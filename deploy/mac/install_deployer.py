"""Bootstrap the outbound-only, main-only deployment agent on the logged-in Mac."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import time

import httpx
from deploy_agent import Runtime, write_json

ROOT = Path(__file__).resolve().parents[2]
HOME = Path.home()
BASE = HOME / 'research-server/deployments'
BASE.mkdir(parents=True, exist_ok=True)
BASE.chmod(0o700)
config = BASE / 'config.json'
write_json(config, {'base': str(BASE), 'repository': 'mark10112/crawl-search', 'branch': 'main', 'poll_seconds': 300})
source = BASE / 'source.git'
if not source.exists():
    subprocess.run(['git', 'clone', '--mirror', 'https://github.com/mark10112/crawl-search.git', str(source)], check=True)

if not (BASE / 'state.json').exists():
    health = httpx.get('http://127.0.0.1:8768/health', timeout=30).json()
    assert health.get('worker_alive') and health.get('ocr_router', {}).get('ok'), 'Baseline must already be healthy'
    baseline = {'sha': health['commit'], 'registered_at': time.time()}
    write_json(BASE / 'state.json', {'current': baseline})
    runtime = Runtime(config)
    try:
        root = runtime.fetch_release(baseline['sha'])
        lock = root / 'deploy/mac/ocr-requirements.lock.txt'
        digest = hashlib.sha256(lock.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
        python = HOME / 'research-server/envs/ocr/bin/python'
        actual = subprocess.check_output(['/opt/homebrew/bin/uv', 'pip', 'freeze', '--python', str(python)], text=True)
        expected = lock.read_text()
        canonical = lambda text: {line.strip().lower().replace('_', '-') for line in text.splitlines() if line.strip() and not line.startswith('#')}
        assert canonical(actual) == canonical(expected), 'Installed baseline OCR versions differ from captured lock'
        write_json(BASE / 'ocr-environments.json', {digest: str(python)})
        runtime.prepare(baseline)
        runtime.save({'current': baseline})
        runtime.publish('baseline_registered', baseline['sha'])
    finally:
        runtime.api.close(); runtime.github.close()

bin_dir = BASE / 'bin'
bin_dir.mkdir(exist_ok=True)
shutil.copy2(ROOT / 'deploy/mac/deploy_agent.py', bin_dir / 'deploy_agent.py')
logs = HOME / 'research-server/logs'
label = 'local.crawl-search.deploy'
plist = HOME / 'Library/LaunchAgents' / (label + '.plist')
spec = {'Label': label, 'ProgramArguments': ['/usr/bin/caffeinate', '-i', str(HOME / 'research-server/envs/ocr/bin/python'),
    str(bin_dir / 'deploy_agent.py'), '--config', str(config)],
    'EnvironmentVariables': {'PATH': '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin', 'PYTHONUNBUFFERED': '1'},
    'RunAtLoad': True, 'StartInterval': 300, 'ThrottleInterval': 60,
    'StandardOutPath': str(logs / 'deploy.log'), 'StandardErrorPath': str(logs / 'deploy.err.log')}
plist.write_bytes(plistlib.dumps(spec)); plist.chmod(0o600)
domain = f'gui/{os.getuid()}'
subprocess.run(['launchctl', 'bootout', domain + '/' + label], capture_output=True)
for _ in range(40):
    if subprocess.run(['launchctl', 'print', domain + '/' + label], capture_output=True).returncode:
        break
    time.sleep(.25)
subprocess.run(['launchctl', 'bootstrap', domain, str(plist)], check=True)
print(json.dumps({'agent': label, 'branch': 'main', 'poll_seconds': 300, 'state': str(BASE / 'state.json')}))
