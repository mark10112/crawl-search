"""Observe the original worker's HTTP/result boundaries without changing its logic."""
import importlib.util,json,sys,threading,time
from http.server import ThreadingHTTPServer
from pathlib import Path
root=Path(sys.argv[1]);work=Path(sys.argv[2]);services=root/'research-tools/local-research/services'
sys.path.insert(0,str(services))
spec=importlib.util.spec_from_file_location('observed_worker',services/'mac_ocr.py');worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
mutex=threading.Lock();original_post=worker.httpx.post;original_ocr=worker.ocr
def current():
    try:return json.loads((work/'current.json').read_text())
    except (OSError,ValueError):return {}
def record(kind,data):
    with mutex:
        with (work/'telemetry.jsonl').open('a') as stream:stream.write(json.dumps({'kind':kind,'time':time.time(),**current(),**data},ensure_ascii=False)+'\n')
def post(url,**kwargs):
    body=kwargs.get('json',{});start=time.perf_counter()
    response=original_post(url,**kwargs)
    try:
        result=response.json();record('generation',{'max_tokens':body.get('max_tokens'),'max_completion_tokens':body.get('max_completion_tokens'),
            'seconds':time.perf_counter()-start,'status':response.status_code,'usage':result.get('usage'),
            'choices':[{'finish_reason':c.get('finish_reason')} for c in result.get('choices',[])]})
    except ValueError:record('generation',{'status':response.status_code,'error':'non-JSON response'})
    return response
def ocr(body):
    try:result=original_ocr(body)
    except Exception as exc:record('page_error',{'error':str(exc)});raise
    record('page',{'result':result});return result
worker.httpx.post=post;worker.ocr=ocr
threading.Thread(target=ThreadingHTTPServer(('127.0.0.1',8112),worker.Proxy).serve_forever,daemon=True).start()
ThreadingHTTPServer(('127.0.0.1',8091),worker.Handler).serve_forever()
