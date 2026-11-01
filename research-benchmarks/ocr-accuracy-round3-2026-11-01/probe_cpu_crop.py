"""Isolated PP-OCRv5 CPU pilot; not the final benchmark and no reference input."""
import hashlib,json,os,time
from pathlib import Path
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK']='True'
from paddleocr import PaddleOCR
W=Path.home()/'research-server/benchmarks/ocr-accuracy-round3-2026-11-01';W.mkdir(parents=True,exist_ok=True)
start=time.perf_counter()
model=PaddleOCR(device='cpu',lang='th',ocr_version='PP-OCRv5',use_doc_orientation_classify=False,use_doc_unwarping=False,use_textline_orientation=False,text_detection_model_name='PP-OCRv5_mobile_det',text_recognition_model_name='th_PP-OCRv5_mobile_rec',enable_mkldnn=False)
setup=time.perf_counter()-start
start=time.perf_counter()
results=list(model.predict(str(W/'actual-failing-crop.png')))
rows=[]
for r in results:
 d=r.json;d=d.get('res',d)
 rows.append(d)
(W/'cpu-crop-pilot.json').write_text(json.dumps({'model':'th_PP-OCRv5_mobile_rec','detector':'PP-OCRv5_mobile_det','setup_seconds':setup,'seconds':time.perf_counter()-start,'results':rows},ensure_ascii=False,indent=2))
print(json.dumps({'setup_seconds':setup,'seconds':time.perf_counter()-start,'results':rows},ensure_ascii=False),flush=True)
