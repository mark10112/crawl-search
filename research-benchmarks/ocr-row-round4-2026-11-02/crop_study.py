"""Diagnostic oracle geometry only: same model/pixels, no answer text in prompts."""
import base64,hashlib,importlib.util,io,json,subprocess,sys,time
from pathlib import Path
import pymupdf
from PIL import Image

root=Path(sys.argv[1]);work=Path(sys.argv[2]);services=root/'research-tools/local-research/services'
sys.path.insert(0,str(services))
spec=importlib.util.spec_from_file_location('crop_worker',services/'mac_ocr.py');worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
assets=Path.home()/'research-server/releases/2026-11-01-ocr/research-benchmarks/real-history-2026-11-01/public-assets'
pdf=pymupdf.open(assets/'us-census.pdf')
source_hash=hashlib.sha256((assets/'us-census.pdf').read_bytes()).hexdigest()
manifest=json.loads((root/'research-benchmarks/real-history-2026-11-01/manifest.json').read_text())
assert source_hash==next(c['sha256'] for c in manifest['cases'] if c['id']=='us-census')
candidate=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
images={n:pdf[n-1].get_pixmap(dpi=300).pil_image().convert('RGB') for n in [2,3]}
tables={2:[302,396,2389,2954],3:[220,252,2339,1046]}
columns={2:[650,797,940,1080,1225,1373],3:[576,733,888,1043,1198,1353]}
# Manually inspected coordinates, selected because four rows failed before.
# Case IDs are opaque and no reference labels or values are loaded here.
cases=[('r1',2,586,616),('r2',2,612,641),('r3',2,1032,1065),('r4',3,1000,1038)]
out=work/'crop-study';out.mkdir(exist_ok=True)
results=[]
def read(image,key,prompt,metadata):
    buffer=io.BytesIO();image.save(buffer,format='PNG');data=buffer.getvalue()
    (out/(key+'.png')).write_bytes(data)
    request={'messages':[{'role':'user','content':[{'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(data).decode()}},{'type':'text','text':prompt}]}]}
    request,_=worker.recognition_request(request)
    start=time.perf_counter()
    try:
        response=worker.stream_recognition('/v1/chat/completions',request)
        if response.status_code!=200:raise RuntimeError('Recognition HTTP '+str(response.status_code))
        raw=response.json()
    except Exception as exc:raw={'error':str(exc)}
    record={'key':key,**metadata,'prompt':prompt,'input_sha256':hashlib.sha256(data).hexdigest(),
            'width':image.width,'height':image.height,'seconds':time.perf_counter()-start,'raw':raw}
    results.append(record)
    (out/'results.json').write_text(json.dumps({'model_revision':worker.REVISION,'candidate':candidate,'source_sha256':source_hash,'temperature':0,
        'max_tokens':8192,'note':'Diagnostic oracle coordinates; not autonomous routing or a corpus score. Same 300-DPI source pixels; no upscaling/cleanup. No reference file loaded. Order whole tables, rows, cells. Single observations.',
        'rows':results},ensure_ascii=False,indent=2))
    print(json.dumps({'crop':key,'seconds':record['seconds'],'finish':raw.get('choices',[{}])[0].get('finish_reason'),'error':raw.get('error')}),flush=True)
for page,box in tables.items():
    read(images[page].crop(box),f'whole-p{page}','Table Recognition:',{'page':page,'scope':'whole','bbox':box})
for case,page,y0,y1 in cases:
    box=[tables[page][0],y0,tables[page][2],y1]
    read(images[page].crop(box),case+'-row','Table Recognition:',{'page':page,'scope':'row','case':case,'bbox':box})
for case,page,y0,y1 in cases:
    for col,(x0,x1) in enumerate(zip(columns[page],columns[page][1:])):
        box=[x0+4,y0,x1-4,y1]
        read(images[page].crop(box),case+f'-c{col+1}','OCR:',{'page':page,'scope':'cell','case':case,'column':col+1,'bbox':box})
