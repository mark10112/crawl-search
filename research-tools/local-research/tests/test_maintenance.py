import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from starlette.testclient import TestClient
from local_research import server_api
from local_research.stack import Settings


class FakeStack:
    def __init__(self, settings=None): self.settings = settings or Settings()
    async def close(self): pass
    async def health(self): return {'searxng': 200, 'ocr_router': {'ok': True}}
    async def read(self, **args): return {'ok': True, 'text': 'Evidence ' * 30}


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'RESEARCH_JOBS_DIR': self.temp.name,
            'LOCAL_RESEARCH_STATE': str(Path(self.temp.name) / 'reader'), 'RESEARCH_START_DRAINED': '0'})
        self.env.start(); self.fake = patch.object(server_api, 'ResearchStack', FakeStack); self.fake.start()
    def tearDown(self):
        self.fake.stop(); self.env.stop(); self.temp.cleanup()
    def test_draining_rejects_new_work_but_allows_internal_probe(self):
        with TestClient(server_api.app) as client:
            self.assertTrue(client.post('/maintenance', json={'action': 'drain'}).json()['draining'])
            self.assertEqual(client.post('/jobs', json={'url': 'https://example.com'}).status_code, 503)
            self.assertEqual(client.post('/read', json={'url': 'https://example.com'}).status_code, 503)
            probe = client.post('/jobs', json={'url': 'https://example.com'}, headers={'X-Research-Deploy-Probe': '1'})
            self.assertEqual(probe.status_code, 200)
            self.assertTrue(client.get('/health').json()['draining'])
            client.post('/maintenance', json={'action': 'resume'})
            self.assertEqual(client.post('/jobs', json={'url': 'https://example.com'}).status_code, 200)
    def test_start_drained_keeps_candidate_closed_until_probe_succeeds(self):
        with patch.dict(os.environ, {'RESEARCH_START_DRAINED': '1'}), TestClient(server_api.app) as client:
            self.assertTrue(client.get('/health').json()['draining'])
            self.assertEqual(client.post('/jobs', json={'url': 'https://example.com'}).status_code, 503)
    def test_invalid_maintenance_action_does_not_drain(self):
        with TestClient(server_api.app) as client:
            self.assertEqual(client.post('/maintenance', json={'action': 'delete'}).status_code, 400)
            self.assertFalse(client.get('/health').json()['draining'])
