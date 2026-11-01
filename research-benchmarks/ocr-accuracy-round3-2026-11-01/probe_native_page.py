import base64,importlib.util,json,os,sys,threading,time
from pathlib import Path
from http.server import ThreadingHTTPServer
import httpx
W=Path.home()/'research-server/benchmarks/ocr-accuracy-round3-2026-11-01'
S=Path.home()/'research-server/experiments/ocr-guard-round2c/research-tools/local-research/services';sys.path.insert(0,str(S))
os.environ['MAC_OCR_MODEL']=str(Path.home()/'.cache/huggingface/hub/models--PaddlePaddle--PaddleOCR-VL-1.6/snapshots/c5630abae1d940eafe0697512a0325494b02ab42')
os.environ['MAC_OCR_STATE']=str(W/'native-page-state');os.environ['PADDLEOCR_VL_MAX_NEW_TOKENS']='8192';os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK']='True'
spec=importlib.util.spec_from_file_location('worker',S/'mac_ocr.py');w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
httpx.post('http://127.0.0.1:8768/maintenance',json={'action':'drain'},timeout=10).raise_for_status()
server=ThreadingHTTPServer(('127.0.0.1',8999),w.Proxy);threading.Thread(target=server.serve_forever,daemon=True).start()
try:
 from paddleocr import PaddleOCRVL
 w.pipeline=PaddleOCRVL(pipeline_version='v1.6',device='cpu',use_doc_orientation_classify=False,use_doc_unwarping=False,vl_rec_backend='mlx-vlm-server',vl_rec_server_url='http://127.0.0.1:8999/',vl_rec_api_model_name=os.environ['MAC_OCR_MODEL'])
 start=time.perf_counter();r=w.ocr({'image_base64':base64.b64encode((W/'gazette-page3-native300.png').read_bytes()).decode(),'cache':False})
 (W/'native-page-pilot.json').write_text(json.dumps({'note':'Original round2c worker, only page input changed from 144 to source 300 DPI; pilot, not timed corpus comparison','seconds':time.perf_counter()-start,'result':r},ensure_ascii=False,indent=2))
 print(json.dumps({'ok':r['ok'],'flags':r['quality_flags'],'seconds':time.perf_counter()-start},ensure_ascii=False),flush=True)
finally:
 server.shutdown();server.server_close();httpx.post('http://127.0.0.1:8768/maintenance',json={'action':'resume'},timeout=10).raise_for_status()
