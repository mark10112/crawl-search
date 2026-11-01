from pathlib import Path
from PIL import Image
from experimental_accuracy import table_grid
W=Path(__file__).parent
for p in sorted(W.glob('us-*-table*.png')):
 r=table_grid(Image.open(p));print(p.name,([len(r[1])-1,len(r[0])-1],r[0],r[1][:15]) if r else None,flush=True)
