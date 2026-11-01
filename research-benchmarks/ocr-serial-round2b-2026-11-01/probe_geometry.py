"""Probe exact captured request; one variable per variant, no reference-based tuning."""
import base64,copy,io,json,time
from PIL import Image,ImageOps
from pathlib import Path
import httpx
W=Path.home()/'research-server/benchmarks/ocr-serial-round2b-2026-11-01'
source=next(W.glob('failed-request-*.json'));failure=json.loads(source.read_text())
rows=[]
httpx.post('http://127.0.0.1:8768/maintenance',json={'action':'drain'},timeout=10).raise_for_status()
try:
    h=httpx.get('http://127.0.0.1:8768/health').json();assert not h['jobs'].get('running',0) and not h['jobs'].get('queued',0)
    item=next(c for c in failure['request']['messages'][0]['content'] if c['type']=='image_url')
    image=Image.open(io.BytesIO(base64.b64decode(item['image_url']['url'].split(',')[1]))).convert('RGB')
    cases=[('upscale-2',image.resize((image.width*2,image.height*2),Image.Resampling.LANCZOS)),('pad-28',ImageOps.expand(image,28,'white')),('upscale-2-pad-28',ImageOps.expand(image.resize((image.width*2,image.height*2),Image.Resampling.LANCZOS),28,'white')),('top-line-pad',ImageOps.expand(image.crop((0,0,image.width,36)),28,'white')),('bottom-line-pad',ImageOps.expand(image.crop((0,36,image.width,image.height)),28,'white'))]
    for name,transformed in cases:
        extra={}
        body=copy.deepcopy(failure['request']);body['max_tokens']=512;body.update(extra)
        buf=io.BytesIO();transformed.save(buf,format='PNG')
        next(c for c in body['messages'][0]['content'] if c['type']=='image_url')['image_url']['url']='data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()
        start=time.perf_counter();r=httpx.post('http://127.0.0.1:8111/v1/chat/completions',json=body,timeout=90);r.raise_for_status()
        row={'variant':name,'changes':extra,'seconds':time.perf_counter()-start,'response':r.json()};rows.append(row)
        (W/'geometry-probe.json').write_text(json.dumps({'source':source.name,'max_tokens':512,'note':'Exact request image and prompt, supplemental one-region diagnostic, not full-document scoring.','rows':rows},ensure_ascii=False,indent=2))
        print(json.dumps(row,ensure_ascii=False),flush=True)
finally:httpx.post('http://127.0.0.1:8768/maintenance',json={'action':'resume'},timeout=10).raise_for_status()
