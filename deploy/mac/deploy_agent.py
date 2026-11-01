"""Pull approved main releases from GitHub; keep runtime and rollback state on Mac."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import time

import httpx

REQUIRED_JOBS = {'Quality (ubuntu-latest)', 'Quality (windows-latest)', 'Quality gate'}


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temp.chmod(0o600)
    temp.replace(path)


def approved_run(runs, jobs, sha, repository, branch='main'):
    """Never fall back to an older success when the newest attempt is not green."""
    if not runs:
        return None
    run = runs[0]
    if not (run.get('head_sha') == sha and run.get('head_branch') == branch
            and run.get('event') == 'push' and run.get('status') == 'completed'
            and run.get('conclusion') == 'success'
            and run.get('head_repository', {}).get('full_name', '').lower() == repository.lower()
            and run.get('path') == '.github/workflows/ci.yml'):
        return None
    passed = {j['name'] for j in jobs if j.get('status') == 'completed' and j.get('conclusion') == 'success'}
    return run if REQUIRED_JOBS <= passed else None


def transition(runtime, state, candidate):
    """Prepare before draining; failed activation/probe restores the prior release."""
    previous = state['current']
    activated = False
    try:
        runtime.prepare(candidate)
        runtime.publish('draining', candidate['sha'])
        runtime.drain()
        activated = True  # A partially failed installer also requires rollback.
        runtime.publish('deploying', candidate['sha'])
        runtime.activate(candidate)
        runtime.probe(candidate)
        runtime.resume()
    except Exception as exc:
        state['last_failed'] = {'sha': candidate['sha'], 'error': str(exc), 'time': time.time()}
        try:
            if activated:
                runtime.publish('rolling_back', candidate['sha'])
                runtime.activate(previous)
                runtime.probe(previous)
            runtime.resume()
            state['last_failed']['rollback_ok'] = True
            runtime.publish('rolled_back' if activated else 'preflight_failed', previous['sha'])
        except Exception as rollback:
            state['last_failed']['rollback_ok'] = False
            state['last_failed']['rollback_error'] = str(rollback)
            runtime.publish('rollback_failed', previous['sha'])
        runtime.save(state)
        return False
    state.update(previous=previous, current={**candidate, 'deployed_at': time.time()})
    state.pop('last_failed', None)
    runtime.save(state)
    runtime.publish('healthy', candidate['sha'])
    return True


class Runtime:
    def __init__(self, config_path):
        self.config_path = Path(config_path)
        self.config = json.loads(self.config_path.read_text())
        self.base = Path(self.config['base']).resolve()
        self.home = self.base.parent
        self.source = self.base / 'source.git'
        self.state_file = self.base / 'state.json'
        self.state = json.loads(self.state_file.read_text())
        self.api = httpx.Client(base_url='http://127.0.0.1:8768', timeout=30)
        self.github = httpx.Client(base_url='https://api.github.com', timeout=30,
            headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'crawl-search-mac-deployer'})

    def save(self, state):
        self.state = state
        write_json(self.state_file, state)

    def publish(self, status, sha):
        value = {'status': status, 'sha': sha, 'time': time.time()}
        write_json(self.base / 'status.json', value)
        with (self.base / 'events.jsonl').open('a') as log:
            log.write(json.dumps(value) + '\n')
        print(json.dumps(value), flush=True)

    def run(self, args, **kwargs):
        return subprocess.run([str(a) for a in args], check=True, timeout=1200, **kwargs)

    def git(self, *args):
        return subprocess.check_output(['git', '--git-dir', str(self.source), *args], text=True, timeout=90).strip()

    def fetch_release(self, sha):
        if not re.fullmatch('[0-9a-f]{40}', sha):
            raise ValueError('Invalid release SHA')
        path = self.base / 'releases' / sha
        if path.exists():
            actual = subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()
            if actual != sha or subprocess.check_output(['git', '-C', str(path), 'status', '--porcelain'], text=True):
                raise RuntimeError('Release checkout is not clean/exact')
        else:
            path.parent.mkdir(exist_ok=True)
            self.run(['git', '--git-dir', self.source, 'worktree', 'add', '--detach', path, sha])
        return path

    def prepare(self, release):
        root = self.fetch_release(release['sha'])
        package = root / 'research-tools/local-research'
        self.run(['/opt/homebrew/bin/uv', 'sync', '--frozen', '--python', '3.12', '--extra', 'browser'], cwd=package)
        py = package / '.venv/bin/python'
        self.run([py, '-m', 'playwright', 'install', 'chromium'])
        self.run([py, '-m', 'patchright', 'install', 'chromium'])
        lock = root / 'deploy/mac/ocr-requirements.lock.txt'
        digest = hashlib.sha256(lock.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
        envs = json.loads((self.base / 'ocr-environments.json').read_text())
        ocr = envs.get(digest)
        if not ocr:
            env = self.base / 'environments' / ('ocr-' + digest[:16])
            env.parent.mkdir(exist_ok=True)
            self.run(['/opt/homebrew/bin/uv', 'venv', '--python', '3.12', env])
            ocr = str(env / 'bin/python')
            self.run(['/opt/homebrew/bin/uv', 'pip', 'sync', '--python', ocr, lock])
            self.run([ocr, '-c', 'import paddleocr,mlx.core,httpx'])
            envs[digest] = ocr
            write_json(self.base / 'ocr-environments.json', envs)
        release.update(path=str(root), ocr_python=ocr)

    def maintenance(self, action):
        response = self.api.post('/maintenance', json={'action': action})
        if response.status_code == 404:  # First upgrade from the pre-CI baseline.
            return None
        response.raise_for_status()
        return response.json()

    def drain(self):
        self.maintenance('drain')
        deadline = time.monotonic() + 900
        while time.monotonic() < deadline:
            # Works for the pre-CI baseline too; no queue schema migration is made.
            with sqlite3.connect(f'file:{self.home}/state/jobs/jobs.sqlite3?mode=ro', uri=True) as db:
                active = db.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0]
            if not active:
                return
            time.sleep(1)
        raise TimeoutError('Jobs did not drain; leaving the previous release active')

    def activate(self, release):
        env = {**os.environ, 'RESEARCH_OCR_PYTHON': release['ocr_python'], 'RESEARCH_START_DRAINED': '1'}
        root = Path(release['path'])
        self.run([root / 'research-tools/local-research/.venv/bin/python', root / 'deploy/mac/install_services.py'], env=env)

    def probe(self, release):
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            try:
                h = self.api.get('/health').json()
                if (h.get('commit') == release['sha'] and h.get('worker_alive')
                        and h.get('searxng') == 200 and h.get('ocr_router', {}).get('ok')):
                    break
            except (httpx.HTTPError, ValueError):
                pass
            time.sleep(1)
        else:
            raise RuntimeError('New service health/commit did not become ready')
        source = Path(release['path']) / 'research-benchmarks/ocr-multilingual-2026-11-01/dataset/english.png'
        r = self.api.post('/uploads', content=source.read_bytes()); r.raise_for_status()
        r = self.api.post('/jobs', json={'upload_id': r.json()['upload_id'], 'cache': False, 'ocr_policy': 'quality'},
            headers={'X-Research-Deploy-Probe': '1'}); r.raise_for_status()
        job = r.json(); deadline = time.monotonic() + 600
        while job['status'] in {'queued', 'running'} and time.monotonic() < deadline:
            time.sleep(.5)
            r = self.api.get('/jobs/' + job['id']); r.raise_for_status(); job = r.json()
        result = job.get('result') or {}
        text = result.get('text', '')
        if not (job['status'] == 'complete' and result.get('ok')
                and all(anchor in text for anchor in ['Research memorandum', '1855', '12,450.75'])):
            raise RuntimeError('Post-deploy English OCR probe failed: ' + str(result.get('error', job['status'])))
        write_json(self.base / 'last-probe.json', {'sha': release['sha'], 'job_id': job['id'], 'result': result})

    def resume(self):
        self.maintenance('resume')

    def check(self, retry=False):
        repository = self.config['repository']
        branch = self.config['branch']
        if branch != 'main' or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
            raise ValueError('Deployment is restricted to configured repository/main')
        remote = 'https://github.com/' + repository + '.git'
        sha = subprocess.check_output(['git', 'ls-remote', remote, 'refs/heads/main'], text=True, timeout=60).split()[0]
        if sha == self.state['current']['sha']:
            return 'current'
        if sha == self.state.get('last_failed', {}).get('sha') and not retry:
            return 'failed-sha-held'
        response = self.github.get(f'/repos/{repository}/actions/workflows/ci.yml/runs',
            params={'branch': branch, 'event': 'push', 'head_sha': sha, 'per_page': 1})
        if response.status_code == 404:
            self.publish('waiting_for_quality', sha)
            return 'workflow-not-installed'
        response.raise_for_status()
        runs = response.json()['workflow_runs']
        jobs = []
        if runs and runs[0].get('conclusion') == 'success':
            response = self.github.get(f'/repos/{repository}/actions/runs/{runs[0]["id"]}/jobs', params={'filter': 'latest', 'per_page': 100})
            response.raise_for_status(); jobs = response.json()['jobs']
        run = approved_run(runs, jobs, sha, repository, branch)
        if not run:
            self.publish('waiting_for_quality', sha)
            return 'quality-not-green'
        self.run(['git', '--git-dir', self.source, 'fetch', 'origin', '+refs/heads/main:refs/remotes/origin/main'])
        if self.git('rev-parse', 'refs/remotes/origin/main') != sha:
            return 'main-moved-recheck-next-cycle'
        # The current baseline/previous release must stay reachable for rollback.
        self.run(['git', '--git-dir', self.source, 'merge-base', '--is-ancestor', self.state['current']['sha'], sha])
        candidate = {'sha': sha, 'workflow_run_id': run['id'], 'workflow_url': run['html_url']}
        return 'deployed' if transition(self, self.state, candidate) else 'failed-restored-or-held'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--retry', action='store_true')
    args = parser.parse_args()
    # The OS releases flock even if the process is killed; no stale lock deletion.
    import fcntl
    lock_path = args.config.parent / 'deploy.lock'
    with lock_path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('Another deployment is running', flush=True)
            return
        runtime = Runtime(args.config)
        try:
            print(runtime.check(retry=args.retry), flush=True)
        finally:
            runtime.api.close(); runtime.github.close()


if __name__ == '__main__':
    main()
