import json,os,signal,time
from pathlib import Path
import psutil
W=Path(__file__).parent;stopped=[]
for p in psutil.process_iter(['pid','name','cmdline']):
    args=p.info['cmdline'] or []
    if p.pid==os.getpid() or not (p.info['name'] or '').lower().startswith('python'):continue
    if any(str(W/name) in args for name in ['probe_native_cells.py','probe_native_cells_v2.py','probe_grid_v3.py']):
        p.terminate();stopped.append(p.pid)
(W/'pilot-process-cleanup.json').write_text(json.dumps({'time':time.time(),'stopped':stopped,'reason':'No CPU probe may compete with the timed corpus run. Stopped partial probes are not counted as benchmark observations.'},indent=2))
print(stopped)
