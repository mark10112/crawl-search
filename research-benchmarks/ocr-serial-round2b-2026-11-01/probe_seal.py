"""Supplemental isolated crop probe. Not part of the primary document benchmark."""
import base64,io,json,time
from pathlib import Path
import httpx,pymupdf
from PIL import Image
W=Path.home()/'research-server/benchmarks/ocr-serial-round2b-2026-11-01'
while not (W/'restored.json').exists():time.sleep(1)
B=Path.home()/'research-server/releases/2026-11-01-ocr/research-benchmarks/real-history-2026-11-01/public-assets'
manifest=json.loads((Path.home()/'research-server/experiments/ocr-serial-round2b/research-benchmarks/real-history-2026-11-01/manifest.json').read_text())['cases']
case=next(c for c in manifest if c['id']=='thai-gazette')
with pymupdf.open(B/case['filename']) as doc:
    image=Image.open(io.BytesIO(doc[2].get_pixmap(dpi=144,alpha=False).tobytes('png')))
crop=image.crop((359,392,461,576));crop.save(W/'gazette-seal-region.png')
buf=io.BytesIO();crop.save(buf,format='PNG');uri='data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()
rows=[]
httpx.post('http://127.0.0.1:8768/maintenance',json={'action':'drain'},timeout=10).raise_for_status()
try:
    h=httpx.get('http://127.0.0.1:8768/health').json();assert not h['jobs'].get('running',0) and not h['jobs'].get('queued',0)
    model=httpx.get('http://127.0.0.1:8111/v1/models').json()['data'][0]['id']
    for prompt in ['Seal Recognition:','OCR:']:
        request={'model':model,'messages':[{'role':'user','content':[{'type':'image_url','image_url':{'url':uri}},{'type':'text','text':prompt}]}], 'max_tokens':1024,'temperature':0,'repetition_penalty':1.0,'repetition_context_size':64}
        start=time.perf_counter();r=httpx.post('http://127.0.0.1:8111/v1/chat/completions',json=request,timeout=120);r.raise_for_status()
        rows.append({'prompt':prompt,'seconds':time.perf_counter()-start,'response':r.json()})
        (W/'seal-probe.json').write_text(json.dumps({'source_id':case['id'],'page':3,'dpi':144,'bbox':[359,392,461,576],'prompt':'OCR:','max_tokens':1024,'note':'Supplemental isolated region; different from full layout/batched inference, not scored as a document.','rows':rows},ensure_ascii=False,indent=2))
        print(json.dumps(rows[-1],ensure_ascii=False),flush=True)
finally:
    httpx.post('http://127.0.0.1:8768/maintenance',json={'action':'resume'},timeout=10).raise_for_status()
