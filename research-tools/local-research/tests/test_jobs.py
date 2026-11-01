import tempfile,unittest
from pathlib import Path
from local_research.jobs import JobStore

class JobsTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.store=JobStore(Path(self.temp.name))
    def tearDown(self):self.store.close();self.temp.cleanup()
    def test_restart_preserves_result_and_recovers_running(self):
        job=self.store.submit({'url':'https://example.org'});self.store.claim();self.store.close();self.store=JobStore(Path(self.temp.name));self.store.recover()
        self.assertEqual(self.store.get(job['id'])['status'],'queued')
        self.store.claim();self.store.finish(job['id'],{'ok':True,'text':'source'})
        self.assertEqual(self.store.get(job['id'])['result']['text'],'source')
    def test_upload_dedup_and_path_rejection(self):
        first=self.store.upload(b'%PDF-test');second=self.store.upload(b'%PDF-test')
        self.assertEqual(first['upload_id'],second['upload_id'])
        with self.assertRaises(ValueError):self.store.asset('../private')
        with self.assertRaises(ValueError):self.store.upload(b'<html>not a document</html>')
    def test_failed_work_not_reported_complete(self):
        job=self.store.submit({'url':'https://example.org'});self.store.claim();self.store.finish(job['id'],{'ok':False,'error':'incomplete'})
        self.assertEqual(self.store.get(job['id'])['status'],'failed')
