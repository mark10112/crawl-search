"""Stop only this run's temporary processes and preserve measured evidence."""
import datetime,json,os,re,signal,sqlite3,time
from pathlib import Path
import httpx,psutil
w=Path.home()/'research-server/benchmarks/mac-vs-firecrawl-2026-11-01'
assert (w/'mac-done.json').exists(),'Wait for the benchmark driver to finish'
with sqlite3.connect(w/'jobs/jobs.sqlite3') as db:
    assert db.execute("select count(*) from jobs where status in ('queued','running')").fetchone()[0]==0
pids=json.loads((w/'processes.json').read_text())
expected={'api':'local_research.server_api','memory':'memory_monitor.py','tunnel':'cloudflared','fixture':'serve.py'}
stopped={}
for name,needle in expected.items():
    try:
        proc=psutil.Process(pids[name]);assert needle in ' '.join(proc.cmdline()),'PID reused; refusing to stop unrelated process'
        proc.terminate();stopped[name]=True
    except psutil.NoSuchProcess:stopped[name]='already-exited'
time.sleep(.5)
config=json.loads((w/'config.json').read_text());cut=datetime.datetime.fromtimestamp(config['started_at']).strftime('%Y-%m-%d %H:%M:%S')
records=[]
for line in (Path.home()/'research-server/logs/mlx.err.log').read_text(errors='replace').splitlines():
    if line[:19]<cut or 'Request completed:' not in line:continue
    values={key:value for key,value in re.findall(r'(generated_tokens|prompt_tokens|finish_reason|elapsed|in_flight)=([^ ]+)',line)}
    values['local_timestamp']=line[:23];records.append(values)
(w/'results/backend-completions.json').write_text(json.dumps(records,indent=2))
for name in ['memory.jsonl','origin-requests.jsonl','config.json','mac.log']:
    (w/'results'/name).write_bytes((w/name).read_bytes())
health=httpx.get('http://127.0.0.1:8768/health',timeout=20).json();assert health['worker_alive'] and health['ocr_router']['ok'] and health['searxng']==200
end={'temporary_processes_stopped':stopped,'production_health':health,'completed_at':time.time()}
(w/'results/cleanup.json').write_text(json.dumps(end,indent=2));print(json.dumps(end))
