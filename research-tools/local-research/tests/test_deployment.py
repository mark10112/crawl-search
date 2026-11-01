import copy
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[3] / 'deploy/mac/deploy_agent.py'
spec = importlib.util.spec_from_file_location('deploy_agent_under_test', path)
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)


class FakeRuntime:
    def __init__(self, failure=None):
        self.failure = failure
        self.activated = []
        self.resumed = False
    def prepare(self, release):
        if self.failure == 'prepare': raise RuntimeError('dependency failure')
    def publish(self, *args): pass
    def save(self, state): self.saved = copy.deepcopy(state)
    def drain(self):
        if self.failure == 'drain': raise TimeoutError('active job')
    def activate(self, release): self.activated.append(release['sha'])
    def probe(self, release):
        if release['sha'] == 'new' and self.failure == 'probe': raise RuntimeError('OCR failed')
        if release['sha'] == 'old' and self.failure == 'rollback': raise RuntimeError('rollback failed')
        if release['sha'] == 'new' and self.failure == 'rollback': raise RuntimeError('candidate failed')
    def resume(self): self.resumed = True


class DeploymentTests(unittest.TestCase):
    def test_newest_run_must_be_successful_push_for_exact_main_sha(self):
        good = {'head_sha': 'abc', 'head_branch': 'main', 'event': 'push', 'status': 'completed',
            'conclusion': 'success', 'head_repository': {'full_name': 'mark10112/crawl-search'}, 'path': '.github/workflows/ci.yml'}
        jobs = [{'name': name, 'status': 'completed', 'conclusion': 'success'} for name in agent.REQUIRED_JOBS]
        self.assertIsNotNone(agent.approved_run([good], jobs, 'abc', 'mark10112/crawl-search'))
        for changed in [{'event': 'pull_request'}, {'head_sha': 'other'}, {'head_branch': 'dev'},
                        {'head_repository': {'full_name': 'someone/fork'}}, {'conclusion': 'failure'}, {'status': 'in_progress'}]:
            bad = {**good, **changed}
            self.assertIsNone(agent.approved_run([bad, good], jobs, 'abc', 'mark10112/crawl-search'))
        self.assertIsNone(agent.approved_run([good], jobs[:-1], 'abc', 'mark10112/crawl-search'))
    def test_success_records_previous_and_resumes(self):
        runtime = FakeRuntime(); state = {'current': {'sha': 'old'}}
        self.assertTrue(agent.transition(runtime, state, {'sha': 'new'}))
        self.assertEqual(state['current']['sha'], 'new')
        self.assertEqual(state['previous']['sha'], 'old')
        self.assertTrue(runtime.resumed)
    def test_bad_post_deploy_probe_rolls_back_and_holds_failed_sha(self):
        runtime = FakeRuntime('probe'); state = {'current': {'sha': 'old'}}
        self.assertFalse(agent.transition(runtime, state, {'sha': 'new'}))
        self.assertEqual(runtime.activated, ['new', 'old'])
        self.assertEqual(state['current']['sha'], 'old')
        self.assertTrue(state['last_failed']['rollback_ok'])
        self.assertEqual(state['last_failed']['sha'], 'new')
    def test_busy_jobs_never_activate_candidate(self):
        runtime = FakeRuntime('drain'); state = {'current': {'sha': 'old'}}
        self.assertFalse(agent.transition(runtime, state, {'sha': 'new'}))
        self.assertEqual(runtime.activated, [])
        self.assertTrue(runtime.resumed)
    def test_rollback_failure_is_not_reported_healthy(self):
        runtime = FakeRuntime('rollback'); state = {'current': {'sha': 'old'}}
        self.assertFalse(agent.transition(runtime, state, {'sha': 'new'}))
        self.assertFalse(state['last_failed']['rollback_ok'])


if __name__ == '__main__': unittest.main()
