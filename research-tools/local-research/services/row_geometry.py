"""Conservative source-image row geometry; no labels or reference answers."""
import numpy as np

def runs(values, gap=1):
    out=[]
    for value in values:
        value=int(value)
        if not out or value-out[-1][-1]>gap+1:out.append([value])
        else:out[-1].append(value)
    return [(g[0],g[-1]+1) for g in out]

def text_lines(image, x0, x1):
    ink=np.asarray(image.convert('L'))[:,x0:x1]<135
    count=ink.sum(axis=1)
    # Long rules are separators, not character lines. Preserve source pixels;
    # this mask is only used to find boundaries, never sent to the recognizer.
    count[count>ink.shape[1]*.72]=0
    groups=runs(np.flatnonzero(count>=max(3,ink.shape[1]*.035)),gap=3 if image.height>700 else 1)
    return [(a,b) for a,b in groups if 3<=b-a<=max(40,image.height*.045)]

def index_rows(image):
    """Detect repeated narrow left IDs + detached right endpoints.

    Require at least five unambiguous pairs; keep complete left-to-right rows
    including multiline titles, rather than the detector's text-only boxes.
    """
    w,h=image.size
    if w<500 or h<700:return []
    ink=np.asarray(image.convert('L'))<135
    gutter=ink[round(h*.2):round(h*.96),round(w*.8):round(w*.87)].mean(axis=0)
    if not len(gutter) or float(np.min(np.convolve(gutter,np.ones(5)/5,mode='valid')))>.012:return []
    left=text_lines(image,round(w*.035),round(w*.15))
    right=text_lines(image,round(w*.87),round(w*.98))
    rows=[]
    for i,(a,b) in enumerate(left):
        end=left[i+1][0] if i+1<len(left) else min(h,b+round(h*.09))
        matches=[r for r in right if r[1]-r[0]>=max(5,h*.006) and a-5<=(r[0]+r[1])/2<end-2]
        if len(matches)!=1 or end-a>h*.16:continue
        y0=max(0,a-6);y1=min(h,end-6)
        rows.append({'bbox':[round(w*.025),y0,round(w*.99),y1],
                     'label_bbox':[round(w*.15),y0,round(w*.86),y1],
                     'value_bbox':[round(w*.86),max(y0,matches[0][0]-4),round(w*.99),min(y1,matches[0][1]+4)]})
    if len(rows)<5:return []
    # A dense ruled table is not this free-standing index layout.
    if len(rows)>30:return []
    projection=ink[rows[0]['bbox'][1]:rows[-1]['bbox'][3]].mean(axis=0)
    possible=runs(np.flatnonzero(projection[round(w*.10):round(w*.24)]<.008),gap=0)
    if not possible:return []
    a,b=max(possible,key=lambda interval:interval[1]-interval[0])
    if b-a<4:return []
    boundary=round(w*.10)+b-8
    for row in rows:
        row['label_bbox'][0]=boundary
        row['id_bbox']=[row['bbox'][0],row['bbox'][1],boundary,row['bbox'][3]]
    return rows

def short_table_rows(image):
    """Split shallow tables at whitespace between first-column text lines."""
    w,h=image.size
    if w<250 or h>600 or w/max(1,h)<4:return []
    lines=text_lines(image,round(w*.025),round(w*.32))
    if not 2<=len(lines)<=8:return []
    if any(b-a>h*.3 for a,b in lines):return []
    cuts=[0]+[(b+c)//2 for (_,b),(c,_) in zip(lines,lines[1:])]+[h]
    if min(b-a for a,b in zip(cuts,cuts[1:]))<5:return []
    return list(zip(cuts,cuts[1:]))
