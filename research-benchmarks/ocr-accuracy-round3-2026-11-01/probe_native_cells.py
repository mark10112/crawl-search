import json,sys,time
from pathlib import Path
from PIL import Image
import numpy as np
W=Path(__file__).parent;sys.path.insert(0,str(W))
from experimental_accuracy import table_grid,recognize_cells
image=Image.open(W/'us-census-p2-table0-native300.png');xs,ys,clean=table_grid(image)
cells=[];inputs=[]
for row,(y0,y1) in enumerate(zip(ys,ys[1:])):
 if row>=25:break
 for col,(x0,x1) in enumerate(zip(xs,xs[1:])):
  crop=clean.crop((x0,y0,x1,y1));pos=np.argwhere(np.asarray(crop)<180)
  if len(pos)<max(4,crop.height*.2):continue
  yy0,xx0=pos.min(axis=0);yy1,xx1=pos.max(axis=0)+1
  crop=crop.crop((int(xx0),int(yy0),int(xx1),int(yy1)))
  inputs.append(crop);cells.append({'row':row,'col':col,'bbox':[x0,y0,x1,y1]})
start=time.perf_counter();results=recognize_cells(inputs)
for c,r in zip(cells,results):c.update(text=r['rec_text'],score=r['rec_score'])
(W/'native-cell-pilot.json').write_text(json.dumps({'note':'First 25 geometric rows, all columns, no reference input, native 300 DPI','seconds':time.perf_counter()-start,'cells':cells},ensure_ascii=False,indent=2))
for row in range(25):print(row,[c['text'] for c in cells if c['row']==row],flush=True)
