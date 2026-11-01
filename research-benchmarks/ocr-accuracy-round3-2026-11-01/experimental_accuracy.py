"""Geometry and finite CPU recognition; no document IDs, labels or reference answers."""
import html,re
import numpy as np
from PIL import Image

MODELS={}
def cpu_model(language):
    if language not in MODELS:
        from paddleocr import TextRecognition
        MODELS[language]=TextRecognition(model_name={'en':'en_PP-OCRv5_mobile_rec','th':'th_PP-OCRv5_mobile_rec'}[language],device='cpu',enable_mkldnn=False)
    return MODELS[language]

def recognize_cells(images,language='en'):
    arrays=[np.asarray(i.convert('RGB'))[:,:,::-1].copy() for i in images]
    return [r.json.get('res',r.json) for r in cpu_model(language).predict(input=arrays,batch_size=32)]

def groups(values):
    result=[]
    for value in values:
        if not result or value>result[-1][-1]+1:result.append([int(value)])
        else:result[-1].append(int(value))
    return result

def table_grid(image):
    import cv2
    gray=np.asarray(image.convert('L'));h,w=gray.shape
    _,ink=cv2.threshold(gray,0,255,cv2.THRESH_BINARY_INV|cv2.THRESH_OTSU)
    extended=cv2.dilate(ink,np.ones((1,5),np.uint8))
    vertical=cv2.morphologyEx(extended,cv2.MORPH_OPEN,np.ones((max(20,min(60,h//5)),1),np.uint8))
    bands=groups(np.flatnonzero((vertical>0).sum(axis=0)>h*.3))
    xs=[0]+[round(sum(g)/len(g)) for g in bands if 4<sum(g)/len(g)<w-4]+[w]
    xs=sorted(set(xs))
    if len(xs)<5 or any(b-a<12 for a,b in zip(xs,xs[1:])):return None
    horizontal=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((1,max(30,w//4)),np.uint8))
    clean=ink.copy();clean[(vertical>0)|(horizontal>0)]=0
    # Row labels provide a clean baseline signal even where dashed empty cells
    # and broken distant rules keep the whole-table projection nonzero.
    labels=clean[:,:max(1,xs[1]-3)]
    count,_,stats,_=cv2.connectedComponentsWithStats((labels>0).astype(np.uint8),8)
    heights=[(r[cv2.CC_STAT_HEIGHT],r[cv2.CC_STAT_AREA]) for r in stats[1:] if 3<=r[cv2.CC_STAT_HEIGHT]<=max(25,h//20) and 1<=r[cv2.CC_STAT_WIDTH]<=max(40,w//20) and r[cv2.CC_STAT_AREA]>=4 and r[cv2.CC_STAT_WIDTH]<=2*r[cv2.CC_STAT_HEIGHT]]
    if not heights:return None
    weighted=sorted(heights);total=sum(a for _,a in weighted);running=0
    for height,area in weighted:
        running+=area
        if running>=total*.5:break
    distance=max(4,round(float(height)*.85),round(float(np.median(np.diff(xs)[1:]))*.14))
    profile=(labels>0).sum(axis=1).astype(float)
    profile=np.convolve(profile,[.25,.5,.25],mode='same')
    candidates=[y for y in range(1,h-1) if profile[y]>=profile[y-1] and profile[y]>=profile[y+1] and profile[y]>=max(4,labels.shape[1]*.03)]
    peaks=[]
    for y in sorted(candidates,key=lambda y:profile[y],reverse=True):
        if all(abs(y-p)>distance for p in peaks):peaks.append(y)
    peaks.sort()
    if len(peaks)<2:return None
    ys=[0]+[(a+b)//2 for a,b in zip(peaks,peaks[1:])]+[h]
    return xs,ys,Image.fromarray(255-clean)

def read_grid(image):
    grid=table_grid(image)
    if grid is None:return None
    xs,ys,clean=grid;cells=[];inputs=[];indices=[]
    for row,(y0,y1) in enumerate(zip(ys,ys[1:])):
        for col,(x0,x1) in enumerate(zip(xs,xs[1:])):
            crop=clean.crop((x0,y0,x1,y1));ink=(np.asarray(crop)<180).mean()
            cell={'row':row,'column':col,'bbox':[x0,y0,x1,y1],'text':'','score':None,'status':'blank-or-rules'}
            if ink>=.008:
                indices.append(len(cells));inputs.append(crop)
            cells.append(cell)
    recognised=recognize_cells(inputs)
    if len(recognised)!=len(indices):raise RuntimeError('Cell recognition count mismatch')
    for index,res in zip(indices,recognised):
        cells[index].update(text=res['rec_text'],score=float(res['rec_score']),status='ctc-decoded')
    rows=[]
    for row in range(len(ys)-1):
        rows.append('<tr>'+''.join('<td>'+html.escape(c['text'])+'</td>' for c in cells if c['row']==row)+'</tr>')
    return {'text':'<table>'+''.join(rows)+'</table>','cells':cells,'columns':len(xs)-1,'rows':len(ys)-1,'x_boundaries':xs,'y_boundaries':ys}
