"""Supplemental one-page preprocessing probe, with exact failed requests captured."""
import base64,hashlib,importlib.util,json,os,sys,time
from pathlib import Path
import httpx
W=Path.home()/'research-server/benchmarks/ocr-serial-round2b-2026-11-01'
root=Path.home()/'research-server/experiments/ocr-serial-round2b'
services=root/'research-tools/local-research/services';sys.path.insert(0,str(services))
os.environ['MAC_OCR_MODEL']=str(Path.home()/'.cache/huggingface/hub/models--PaddlePaddle--PaddleOCR-VL-1.6/snapshots/c5630abae1d940eafe0697512a0325494b02ab42')
os.environ['MAC_OCR_STATE']=str(W/'unmerged-probe-state');os.environ['PADDLEOCR_VL_MAX_NEW_TOKENS']='8192'
spec=importlib.util.spec_from_file_location('probe_worker',services/'mac_ocr.py');w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
from http.server import ThreadingHTTPServer
import threading
server=None
httpx.post('http://127.0.0.1:8768/maintenance',json={'action':'drain'},timeout=10).raise_for_status()
import subprocess
uid=str(os.getuid());domain='gui/'+uid
stopped=False
try:
    h=httpx.get('http://127.0.0.1:8768/health').json();assert not h['jobs'].get('running',0) and not h['jobs'].get('queued',0)
    subprocess.run(['launchctl','bootout',domain+'/local.crawl-search.ocr'],check=True);stopped=True;time.sleep(1)
    server=ThreadingHTTPServer(('127.0.0.1',8999),w.Proxy)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    from paddleocr import PaddleOCRVL
    actual=PaddleOCRVL(pipeline_version='v1.6',device='cpu',use_doc_orientation_classify=False,use_doc_unwarping=False,vl_rec_backend='mlx-vlm-server',vl_rec_server_url='http://127.0.0.1:8999/',vl_rec_api_model_name=os.environ['MAC_OCR_MODEL'])
    class Unmerged:
        def predict(self,path,**kwargs):return actual.predict(path,merge_layout_blocks=False,**kwargs)
    w.pipeline=Unmerged()
    original=w.httpx.post
    def post(url,**kwargs):
        r=original(url,**kwargs)
        if ':8111' in url and r.status_code==200 and any(c.get('finish_reason')!='stop' for c in r.json().get('choices',[])):
            body=kwargs['json'];ident=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()
            (W/('failed-request-'+ident+'.json')).write_text(json.dumps({'request':body,'response':r.json()},ensure_ascii=False))
        return r
    w.httpx.post=post
    image=(W/'gazette-page3.png').read_bytes();start=time.perf_counter()
    result=w.ocr({'image_base64':base64.b64encode(image).decode(),'cache':False})
    (W/'unmerged-probe.json').write_text(json.dumps({'note':'Supplemental page 3 only, merge_layout_blocks=False; not a full-document score.','seconds':time.perf_counter()-start,'result':result},ensure_ascii=False,indent=2))
    print(json.dumps({'ok':result['ok'],'seconds':time.perf_counter()-start,'flags':result['quality_flags']},ensure_ascii=False),flush=True)
finally:
    if server:server.shutdown();server.server_close()
    if stopped:subprocess.run(['launchctl','bootstrap',domain,str(Path.home()/'Library/LaunchAgents/local.crawl-search.ocr.plist')],check=True)
    httpx.post('http://127.0.0.1:8768/maintenance',json={'action':'resume'},timeout=10).raise_for_status()
