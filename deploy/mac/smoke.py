"""Exercise Mac API locally; Windows MCP forwarding is tested separately."""
import json,time
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[2]
OUT=Path.home()/'research-server/validation';OUT.mkdir(exist_ok=True)
with httpx.Client(base_url='http://127.0.0.1:8768',timeout=30) as client:
    health=client.get('/health').json();print(json.dumps({'health':health}),flush=True)
    search=client.post('/search',json={'query':'SearXNG search API documentation','limit':3,'cache':False}).json()
    print(json.dumps({'search_ok':search.get('ok'),'results':len(search.get('results',[])),'errors':search.get('engine_errors')}),flush=True)
    data=(ROOT/'research-benchmarks/ocr-multilingual-2026-11-01/dataset/english.png').read_bytes()
    upload=client.post('/uploads',content=data).json();job=client.post('/jobs',json={'upload_id':upload['upload_id'],'ocr_policy':'quality','cache':False}).json()
    start=time.monotonic();ident=job['id'];print(json.dumps({'job_id':ident}),flush=True)
    # Recreate the client to show that the job is not owned by the submitting connection.
with httpx.Client(base_url='http://127.0.0.1:8768',timeout=30) as client:
    while job['status'] in {'queued','running'} and time.monotonic()-start<900:
        time.sleep(1);job=client.get('/jobs/'+ident).json()
    (OUT/'api-smoke.json').write_text(json.dumps({'health':health,'search':search,'upload':upload,'job':job},ensure_ascii=False,indent=2))
    print(json.dumps({'status':job['status'],'seconds':round(time.monotonic()-start,2),'result':job.get('result')},ensure_ascii=False),flush=True)
    assert job['status']=='complete',job
