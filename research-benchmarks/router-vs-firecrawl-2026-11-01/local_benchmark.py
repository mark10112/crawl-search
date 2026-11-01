import argparse
import json
import time
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--base-url',required=True)
    parser.add_argument('--phase',choices=['warmup','off','prime','hit','all'],default='all')
    parser.add_argument('--only',default=None)
    parser.add_argument('--policy',choices=['balanced','quality'],default='balanced')
    args=parser.parse_args()
    cases=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))['cases']
    if args.only:cases=[case for case in cases if case['id']==args.only]
    results=ROOT/'results'
    results.mkdir(exist_ok=True)
    rows=[]
    phases=['off','prime','hit'] if args.phase=='all' else [args.phase]
    with httpx.Client(timeout=240) as client:
        if args.phase=='warmup':
            for filename in ['english.pdf','dynamic-english.html']:
                result=client.post('http://127.0.0.1:8768/read',json={'url':args.base_url+'/'+filename,
                    'cache':False,'max_pages':1,'ocr_policy':'quality'}).json()
                print(json.dumps({'warmup':filename,'ok':result.get('ok'),'reader':result.get('reader'),'error':result.get('error')},ensure_ascii=False),flush=True)
            return
        for phase in phases:
            for case in cases:
                request={'url':args.base_url+'/'+case['filename'],'cache':phase!='off','max_pages':1,'ocr_policy':args.policy}
                started=time.time()*1000
                clock=time.perf_counter()
                response=client.post('http://127.0.0.1:8768/read',json=request)
                elapsed=round((time.perf_counter()-clock)*1000,2)
                try:raw=response.json()
                except ValueError:raw={'ok':False,'error':response.text}
                provider='local-quality' if args.policy=='quality' else 'local'
                row={'provider':provider,'id':case['id'],'phase':phase,'request':request,'started_ms':started,
                     'ended_ms':time.time()*1000,'elapsed_ms':elapsed,'raw':raw,'credits_used':raw.get('credits_used',0)}
                rows.append(row)
                (results/f"{provider}-{phase}-{case['id']}.json").write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf-8')
                print(json.dumps({'id':case['id'],'phase':phase,'ok':raw.get('ok'),'elapsed_ms':elapsed,
                                  'reader':raw.get('reader'),'cache_hit':raw.get('cache_hit'),
                                  'fallback':raw.get('external_fallback_required'),'error':raw.get('error')},ensure_ascii=False),flush=True)
    (results/'local-run.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
