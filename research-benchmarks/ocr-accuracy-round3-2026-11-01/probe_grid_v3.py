"""CPU cell grid pilot, all cells, no reference access."""
import json,sys,time
from pathlib import Path
from PIL import Image
W=Path.home()/'research-server/benchmarks/ocr-accuracy-round3-2026-11-01';sys.path.insert(0,str(W))
from experimental_accuracy import read_grid
rows=[]
for path in sorted(W.glob('us-*-table*.png')):
 start=time.perf_counter();result=read_grid(Image.open(path))
 rows.append({'file':path.name,'seconds':time.perf_counter()-start,'result':result})
 (W/'grid-v3-pilot.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
 print(json.dumps({'file':path.name,'seconds':rows[-1]['seconds'],'shape':[result['rows'],result['columns']] if result else None}),flush=True)
