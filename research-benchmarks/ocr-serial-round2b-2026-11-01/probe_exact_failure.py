"""Probe exact captured request; one variable per variant, no reference-based tuning."""
import copy,json,time
from pathlib import Path
import httpx
W=Path.home()/'research-server/benchmarks/ocr-serial-round2b-2026-11-01'
source=next(W.glob('failed-request-*.json'));failure=json.loads(source.read_text())
rows=[]
httpx.post('http://127.0.0.1:8768/maintenance',json={'action':'drain'},timeout=10).raise_for_status()
try:
    h=httpx.get('http://127.0.0.1:8768/health').json();assert not h['jobs'].get('running',0) and not h['jobs'].get('queued',0)
    for name,extra in [('penalty-1.1',{'repetition_penalty':1.1}),('penalty-1.15',{'repetition_penalty':1.15}),('min-pixels-112896',{'min_pixels':112896})]:
        body=copy.deepcopy(failure['request']);body['max_tokens']=512;body.update(extra)
        start=time.perf_counter();r=httpx.post('http://127.0.0.1:8111/v1/chat/completions',json=body,timeout=90);r.raise_for_status()
        row={'variant':name,'changes':extra,'seconds':time.perf_counter()-start,'response':r.json()};rows.append(row)
        (W/'exact-failure-probe.json').write_text(json.dumps({'source':source.name,'max_tokens':512,'note':'Exact request image and prompt, supplemental one-region diagnostic, not full-document scoring.','rows':rows},ensure_ascii=False,indent=2))
        print(json.dumps(row,ensure_ascii=False),flush=True)
finally:httpx.post('http://127.0.0.1:8768/maintenance',json={'action':'resume'},timeout=10).raise_for_status()
