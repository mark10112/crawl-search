"""Fixed geometry-only table bands, all rows retained; no reference answers loaded."""
import base64,io,json,time
from pathlib import Path
import httpx,numpy as np
from PIL import Image
W=Path.home()/'research-server/benchmarks/ocr-accuracy-round3-2026-11-01'
rows=[]
httpx.post('http://127.0.0.1:8768/maintenance',json={'action':'drain'},timeout=10).raise_for_status()
try:
 model=httpx.get('http://127.0.0.1:8111/v1/models').json()['data'][0]['id']
 for file in ['us-census-p2-table0.png','us-preservation-p3-table0.png','us-preservation-p3-table2.png']:
  image=Image.open(W/file).convert('RGB');arr=np.array(image.convert('L'));ink=(arr<170).mean(axis=1);cuts=[0]
  while image.height-cuts[-1]>320:
   target=cuts[-1]+260;lo=target-45;hi=min(image.height-1,target+45)
   options=[y for y in range(lo,hi) if ink[y]<.035]
   cut=min(options,key=lambda y:abs(y-target)) if options else min(range(lo,hi),key=lambda y:ink[y])
   cuts.append(cut)
  cuts.append(image.height)
  for a,b in zip(cuts,cuts[1:]):
   crop=image.crop((0,a,image.width,b));crop=crop.resize((round(crop.width*1.5),round(crop.height*1.5)),Image.Resampling.LANCZOS)
   buf=io.BytesIO();crop.save(buf,format='PNG');uri='data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()
   body={'model':model,'messages':[{'role':'user','content':[{'type':'image_url','image_url':{'url':uri}},{'type':'text','text':'Table Recognition:'}]}],'max_tokens':8192,'temperature':0}
   start=time.perf_counter();r=httpx.post('http://127.0.0.1:8111/v1/chat/completions',json=body,timeout=180);r.raise_for_status()
   rows.append({'file':file,'y':[a,b],'scale':1.5,'seconds':time.perf_counter()-start,'response':r.json()})
   (W/'table-pilot.json').write_text(json.dumps({'note':'geometry-only pilot; fixed 260px target bands, no reference input','rows':rows},ensure_ascii=False,indent=2))
   print(json.dumps({'file':file,'y':[a,b],'seconds':rows[-1]['seconds'],'finish':r.json()['choices'][0]['finish_reason']},ensure_ascii=False),flush=True)
finally:httpx.post('http://127.0.0.1:8768/maintenance',json={'action':'resume'},timeout=10).raise_for_status()
