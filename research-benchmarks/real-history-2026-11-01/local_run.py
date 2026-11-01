import json,time,hashlib
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parent
BASE='https://moses-initially-assigned-mining.trycloudflare.com'
cases=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))['cases']
(ROOT/'reference-lock.json').write_text(json.dumps({'sha256':hashlib.sha256((ROOT/'references.json').read_bytes()).hexdigest(),'locked_at':time.time(),'before_provider_runs':True},indent=2),encoding='utf-8')
with httpx.Client(timeout=600) as client:
    for phase in ['off','prime','hit','forced-quality']:
        for case in cases:
            request={'url':BASE+'/'+case['filename'],'cache':phase in ['prime','hit'],'max_pages':3,'max_chars':40000,
                'mode':'ocr' if phase=='forced-quality' else 'auto','ocr_policy':'quality' if phase=='forced-quality' else 'balanced'}
            started=time.time();clock=time.perf_counter()
            try:
                response=client.post('http://127.0.0.1:8768/read',json=request);raw=response.json()
            except Exception as e:raw={'ok':False,'error':str(e)}
            elapsed=round((time.perf_counter()-clock)*1000,2)
            row={'provider':'local-forced-quality' if phase=='forced-quality' else 'local','phase':'off' if phase=='forced-quality' else phase,
                'id':case['id'],'request':request,'elapsed_ms':elapsed,'started_at':started,'raw':raw,'credits_used':0}
            target=ROOT/'results'/f"{row['provider']}-{row['phase']}-{case['id']}.json"
            target.write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({'id':case['id'],'phase':phase,'ok':raw.get('ok'),'reader':raw.get('reader'),'elapsed_ms':elapsed,
                              'cache_hit':raw.get('cache_hit'),'chars':raw.get('extracted_chars'),'error':raw.get('error')},ensure_ascii=False),flush=True)
