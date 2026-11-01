from pathlib import Path
from PIL import Image,ImageDraw
from experimental_accuracy import table_grid
W=Path(__file__).parent;p=W/'us-census-p2-table0-native300.png';image=Image.open(p).convert('RGB');xs,ys,clean=table_grid(image)
draw=ImageDraw.Draw(image)
for x in xs:draw.line((x,0,x,image.height),fill='red',width=1)
for y in ys:draw.line((0,y,image.width,y),fill='blue',width=1)
image.crop((0,0,min(image.width,1200),700)).save(W/'grid-overlay-native.png')
print(len(ys)-1,len(xs)-1,ys[:25])
