"""Source pixels only: trim dominant text line, then optionally add white border."""
import numpy as np
from PIL import ImageOps

def dominant_bbox(image):
    dark=np.asarray(image.convert('L'))<160
    h,w=dark.shape;seen=np.zeros_like(dark);components=[]
    for y,x in zip(*np.nonzero(dark)):
        y=int(y);x=int(x)
        if seen[y,x]:continue
        stack=[(x,y)];seen[y,x]=True;points=[]
        while stack:
            a,b=stack.pop();points.append((a,b))
            for v in range(max(0,b-1),min(h,b+2)):
                for u in range(max(0,a-1),min(w,a+2)):
                    if dark[v,u] and not seen[v,u]:seen[v,u]=True;stack.append((u,v))
        xs,ys=zip(*points)
        components.append({'box':[min(xs),min(ys),max(xs)+1,max(ys)+1],'area':len(points)})
    if not components:raise ValueError('No foreground pixels')
    anchor=max(components,key=lambda c:c['area']);a=anchor['box']
    selected=[c['box'] for c in components if c['area']>=max(3,anchor['area']*.025)
              and c['box'][3]-c['box'][1]>=3
              and a[1]-3<=(c['box'][1]+c['box'][3])/2<=a[3]+3]
    return [min(b[0] for b in selected),min(b[1] for b in selected),max(b[2] for b in selected),max(b[3] for b in selected)]

def variants(image):
    box=dominant_bbox(image)
    return [('original',image.copy(),[0,0,image.width,image.height],0),
            ('original_pad10',ImageOps.expand(image,border=10,fill='white'),[0,0,image.width,image.height],10),
            ('tight',image.crop(box),box,0),
            ('tight_pad10',ImageOps.expand(image.crop(box),border=10,fill='white'),box,10)]
