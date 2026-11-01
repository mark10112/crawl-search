"""Freeze old crop pixels and download official, pinned recognizer data."""
import hashlib,json,subprocess,sys,urllib.request
from pathlib import Path
import pymupdf
from PIL import Image

ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
WORK=Path.home()/'research-server/benchmarks/ocr-backup-round5-2026-11-02'
WORK.mkdir(parents=True,exist_ok=True);OUT=WORK/'inputs';OUT.mkdir(exist_ok=True)
assert not (WORK/'inputs.json').exists(),'Do not overwrite frozen inputs'
old=ROOT/'research-benchmarks/ocr-row-round4-2026-11-02'
references=json.loads((ROOT/'research-benchmarks/real-history-2026-11-01/references.json').read_text())
locked=hashlib.sha256(json.dumps(references,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
assert locked=='72a37213b39a3a3dd1b4e344162d962b39c3c460fcad2bf2dfea105620301ac2'
assets=Path.home()/'research-server/releases/2026-11-01-ocr/research-benchmarks/real-history-2026-11-01/public-assets'
manifest=json.loads((ROOT/'research-benchmarks/real-history-2026-11-01/manifest.json').read_text())
assert hashlib.sha256((assets/'thai-gazette.pdf').read_bytes()).hexdigest()==next(c['sha256'] for c in manifest['cases'] if c['id']=='thai-gazette')
pdf=pymupdf.open(assets/'thai-gazette.pdf')
pages={n:pdf[n-1].get_pixmap(dpi=300).pil_image().convert('RGB') for n in [1,2,3]}
specs=[(1,[1103,845,1270,871]),(1,[1103,1480,1270,1506]),(2,[1118,520,1287,545]),
       (2,[1118,600,1287,624]),(3,[1118,429,1287,457]),(3,[1118,1620,1287,1653])]
inputs=[];expected=[]
def add(key,data,group,language,provenance,value):
    file=OUT/(key+'.png');file.write_bytes(data)
    inputs.append({'id':key,'file':file.name,'group':group,'language':language,'sha256':hashlib.sha256(data).hexdigest(),
                   'size':list(Image.open(file).size),'provenance':provenance})
    expected.append({'id':key,'expected':value})
for i,(page,box) in enumerate(specs):
    file=OUT/f'g{i+1}.png';pages[page].crop(box).save(file)
    data=file.read_bytes()
    if i==0:assert hashlib.sha256(data).hexdigest()=='7120aa4d5c51426815179501000d00a71730501697a87b970008d889e34376d4'
    if i==4:assert hashlib.sha256(data).hexdigest()=='5441c8db5798afa21905e3d392a39fdc7a8a49cac9db19875271a8d15eae2b99'
    add('g'+str(i+1),data,'gazette','tha',{'page':page,'bbox':box,'kind':'reconstructed-frozen-round4-geometry',
        'previous_request_byte_hash_verified':i in [0,4]},references['table_rows'][i]['values'][0])
study=json.loads((old/'crop-study/results.json').read_text())
for name,label,col in [('r1-c3','Adams',2),('r3-c1','Cook',0),('r4-c5','Woodford',4)]:
    row=next(r for r in study['rows'] if r['key']==name)
    data=(old/'crop-study'/(name+'.png')).read_bytes();assert hashlib.sha256(data).hexdigest()==row['input_sha256']
    value=next(r['values'][col] for r in references['table_rows'] if r['document']=='us-census' and r['label']==label)
    add(name,data,'census','eng',{'kind':'byte-identical-round4-file','bbox':row['bbox'],'page':row['page']},value)
(WORK/'inputs.json').write_text(json.dumps({'reference_hash':locked,'inputs':inputs},indent=2))
(WORK/'references.json').write_text(json.dumps({'reference_hash':locked,'values':expected},ensure_ascii=False,indent=2))
weights=Path.home()/'research-server/models/tesseract-round5';weights.mkdir(parents=True,exist_ok=True)
models={}
for name in ['fast','best']:
    repo='https://github.com/tesseract-ocr/tessdata_'+name+'.git'
    revision=subprocess.check_output(['git','ls-remote',repo,'refs/heads/main'],text=True).split()[0]
    folder=weights/name;folder.mkdir(exist_ok=True);files=[]
    for language in ['tha','eng']:
        url=f'https://raw.githubusercontent.com/tesseract-ocr/tessdata_{name}/{revision}/{language}.traineddata'
        file=folder/(language+'.traineddata')
        data=urllib.request.urlopen(url,timeout=90).read();assert len(data)>100000
        file.write_bytes(data);files.append({'language':language,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'url':url})
    models['tesseract_'+name]={'revision':revision,'files':files}
for language in ['th','en']:
    model=language+'_PP-OCRv5_mobile_rec';folder=Path.home()/'.paddlex/official_models'/model
    models[model]={'files':[{'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
                          for p in sorted(folder.iterdir()) if p.is_file()]}
models['tesseract_version']=subprocess.check_output(['/opt/homebrew/bin/tesseract','--version'],text=True,stderr=subprocess.STDOUT)
models['os']=subprocess.check_output(['sw_vers'],text=True)
(WORK/'models.json').write_text(json.dumps(models,indent=2))
print(json.dumps({'inputs':len(inputs),'reference_hash':locked,'model_data_frozen':list(models)}),flush=True)
