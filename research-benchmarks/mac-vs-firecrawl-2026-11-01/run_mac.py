import hashlib,json,sys,time
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parent
work=Path(sys.argv[1]);base=sys.argv[2];manifest=json.loads((ROOT.parent/'real-history-2026-11-01/manifest.json').read_text())
out=work/'results';out.mkdir(exist_ok=True)
with httpx.Client(base_url='http://127.0.0.1:8778',timeout=30) as client:
    for phase in ['off','prime','hit','forced-quality']:
        for case in manifest['cases']:
            provider='mac-forced-quality' if phase=='forced-quality' else 'mac'
            label='off' if phase=='forced-quality' else phase
            request={'url':base+'/'+case['filename'],'cache':phase in ['prime','hit'],'max_pages':3,'max_chars':40000,
                'mode':'ocr' if phase=='forced-quality' else 'auto','ocr_policy':'quality' if phase=='forced-quality' else 'balanced'}
            started=time.time();clock=time.perf_counter();job=None
            try:
                r=client.post('/jobs',json=request);r.raise_for_status();job=r.json()
                while job['status'] in {'queued','running'}:
                    if time.perf_counter()-clock>1200:raise TimeoutError('Benchmark wait exceeded 1200s; retain job ID')
                    time.sleep(.1);r=client.get('/jobs/'+job['id']);r.raise_for_status();job=r.json()
                raw=job.get('result') or {'ok':False,'error':'Job ended without result'}
            except Exception as e:raw={'ok':False,'error':str(e),'pending_job':job['id'] if job else None}
            row={'provider':provider,'phase':label,'id':case['id'],'request':request,'started_at':started,'ended_at':time.time(),
                'elapsed_ms':round((time.perf_counter()-clock)*1000,2),'raw':raw,'credits_used':0,'job':job}
            if raw.get('content_sha256') and raw['content_sha256']!=case['sha256']:raise RuntimeError('Source hash changed')
            (out/f'{provider}-{label}-{case["id"]}.json').write_text(json.dumps(row,ensure_ascii=False,indent=2))
            print(json.dumps({'provider':provider,'phase':label,'id':case['id'],'ok':raw.get('ok'),'seconds':row['elapsed_ms']/1000,
                'cache_hit':raw.get('cache_hit'),'error':raw.get('error')},ensure_ascii=False),flush=True)
(work/'mac-done.json').write_text(json.dumps({'time':time.time()}))
