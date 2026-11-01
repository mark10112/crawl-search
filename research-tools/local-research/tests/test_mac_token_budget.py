import base64,importlib.util,io,os,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image

class TokenBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        services=Path(__file__).resolve().parents[1]/'services'
        spec=importlib.util.spec_from_file_location('mac_worker_budget_test',services/'mac_ocr.py')
        self.worker=importlib.util.module_from_spec(spec)
        sys.path.insert(0,str(services))
        try:
            with patch.dict(os.environ,{'MAC_OCR_MODEL':'test-model','MAC_OCR_STATE':self.temp.name,'PADDLEOCR_VL_MAX_NEW_TOKENS':'8192'}):
                spec.loader.exec_module(self.worker)
        finally:sys.path.pop(0)
        self.requests=[]
        def predict(path,**kwargs):
            self.requests.append(kwargs)
            self.worker.calls.append({'finish_reason':'stop','tokens':30})
            return [SimpleNamespace(markdown={'markdown_texts':'The council reviewed revenue and expenditure records for public research.'},json={'res':{'parsing_res_list':[]}})]
        self.worker.pipeline=SimpleNamespace(predict=predict)
        stream=io.BytesIO();Image.new('RGB',(20,20),'white').save(stream,format='PNG')
        self.body={'image_base64':base64.b64encode(stream.getvalue()).decode(),'cache':True}
    def tearDown(self):self.temp.cleanup()
    def test_predict_receives_explicit_budget_instead_of_pipeline_default(self):
        result=self.worker.ocr(self.body)
        self.assertTrue(result['ok'])
        self.assertEqual(self.requests[0]['max_new_tokens'],8192)
    def test_proxy_forwards_penalty_without_losing_token_ceiling(self):
        body,requested=self.worker.recognition_request({'max_completion_tokens':10000,'messages':[]})
        self.assertEqual(requested,10000)
        self.assertEqual(body['max_tokens'],8192)
        self.assertEqual(body['repetition_penalty'],1.05)
        self.assertEqual(body['repetition_context_size'],64)
        self.assertNotIn('max_completion_tokens',body)
    def test_budget_change_cannot_reuse_old_page_result(self):
        self.worker.MAX_NEW_TOKENS=4096
        self.worker.ocr(self.body)
        self.worker.MAX_NEW_TOKENS=8192
        second=self.worker.ocr(self.body)
        self.assertFalse(second['cache_hit'])
        self.assertEqual(len(self.requests),2)
        third=self.worker.ocr(self.body)
        self.assertTrue(third['cache_hit'])
        self.assertEqual(len(self.requests),2)
