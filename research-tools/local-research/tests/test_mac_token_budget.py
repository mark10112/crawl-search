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
        self.assertEqual(body['repetition_penalty'],1.0)
        self.assertEqual(body['repetition_context_size'],64)
        self.assertNotIn('max_completion_tokens',body)
    def test_concurrent_regions_do_not_overlap_in_mlx(self):
        import threading,time
        from concurrent.futures import ThreadPoolExecutor
        active=0;peak=0;guard=threading.Lock();start=threading.Barrier(4)
        def post(*args,**kwargs):
            nonlocal active,peak
            with guard:active+=1;peak=max(peak,active)
            time.sleep(.02)
            with guard:active-=1
            return SimpleNamespace(status_code=200)
        def request(_):
            start.wait()
            return self.worker.forward_recognition('/v1/chat/completions',{'messages':[]})
        # Exercise the real forwarding boundary, including concurrent callers.
        class Client:
            def __init__(self,*args,**kwargs):pass
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def stream(self,*args,**kwargs):
                post()
                class Response:
                    status_code=200
                    def __enter__(self):return self
                    def __exit__(self,*args):pass
                    def iter_lines(self):return iter(['data: {"choices":[{"delta":{"content":"hello"},"finish_reason":"stop"}]}','data: [DONE]'])
                return Response()
        with patch.object(self.worker.httpx,'Client',Client):
            with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(request,range(4)))
        self.assertEqual(peak,1)
        self.assertTrue(all(r.status_code==200 for r in results))
    def test_stream_guard_stops_consuming_and_never_reports_success(self):
        import json
        def lines():
            yield 'data: '+json.dumps({'choices':[{'delta':{'content':'W.A.T. '+'0'*150},'finish_reason':None}]})
            raise AssertionError('The runaway stream must be closed without consuming more tokens')
        result=self.worker.collect_stream(lines())
        self.assertTrue(result['repetition_guard'])
        self.assertEqual(result['choices'][0]['finish_reason'],'length')
        self.assertIsNone(result['usage']['completion_tokens'])
        self.assertFalse(result['token_usage_complete'])
    def test_normal_stream_keeps_full_text_and_final_token_usage(self):
        import json
        events=[{'choices':[{'delta':{'content':'Public revenue records and expenditure evidence.'},'finish_reason':None}]},
                {'choices':[{'delta':{},'finish_reason':'stop'}]},
                {'choices':[],'usage':{'completion_tokens':9}}]
        result=self.worker.collect_stream(['data: '+json.dumps(e) for e in events]+['data: [DONE]'])
        self.assertFalse(result['repetition_guard'])
        self.assertEqual(result['usage']['completion_tokens'],9)
        self.assertEqual(result['choices'][0]['message']['content'],events[0]['choices'][0]['delta']['content'])
    def test_missing_stream_finish_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'without a finish reason'):
            self.worker.collect_stream(['data: [DONE]'])
    def test_budget_change_cannot_reuse_old_page_result(self):
        self.worker.MAX_NEW_TOKENS=4096
        self.worker.ocr(self.body)
        self.worker.MAX_NEW_TOKENS=8192
        second=self.worker.ocr(self.body)
        self.assertFalse(second['cache_hit'])
        self.assertEqual(len(self.requests),2)
    def test_recognition_profiles_cannot_share_page_cache(self):
        detail=self.worker.ocr({**self.body,'recognition_profile':'detail'})
        baseline=self.worker.ocr({**self.body,'recognition_profile':'baseline'})
        self.assertFalse(detail['cache_hit']);self.assertFalse(baseline['cache_hit'])
        self.assertEqual(baseline['recognition_profile'],'baseline')
        self.assertEqual(len(self.requests),2)
        third=self.worker.ocr(self.body)
        self.assertTrue(third['cache_hit'])
        self.assertEqual(len(self.requests),2)
