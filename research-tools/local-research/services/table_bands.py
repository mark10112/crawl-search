"""Split dense tables at image whitespace, preserving every source pixel."""
import base64,copy,hashlib,io,json,re
import numpy as np
from PIL import Image

def request_image(body):
    for message in body.get('messages',[]):
        for item in message.get('content',[]):
            if isinstance(item,dict) and item.get('type')=='image_url':
                uri=item.get('image_url',{}).get('url','')
                if uri.startswith('data:image/') and ';base64,' in uri:
                    return Image.open(io.BytesIO(base64.b64decode(uri.split(',',1)[1]))).convert('RGB')
    return None

def is_table(body):
    return any(item.get('type')=='text' and item.get('text','').strip()=='Table Recognition:'
               for message in body.get('messages',[]) for item in message.get('content',[]) if isinstance(item,dict))

def bands(image):
    if image.width*image.height<=800000 or image.height<=640:return [(0,image.height)]
    target=max(100,min(520,1000000//max(1,image.width)))
    ink=(np.asarray(image.convert('L'))<170).mean(axis=1);cuts=[0]
    while image.height-cuts[-1]>target+target//4:
        center=cuts[-1]+target;lo=max(cuts[-1]+1,center-target//6);hi=min(image.height-1,center+target//6)
        whitespace=[y for y in range(lo,hi) if ink[y]<.035]
        cut=min(whitespace,key=lambda y:abs(y-center)) if whitespace else min(range(lo,hi),key=lambda y:ink[y])
        cuts.append(cut)
    cuts.append(image.height)
    return list(zip(cuts,cuts[1:]))

def tile_request(body,image,interval):
    a,b=interval;crop=image.crop((0,a,image.width,b));buf=io.BytesIO();crop.save(buf,format='PNG')
    result=copy.deepcopy(body)
    for message in result['messages']:
        for item in message.get('content',[]):
            if item.get('type')=='image_url':item['image_url']['url']='data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()
    return result,hashlib.sha256(buf.getvalue()).hexdigest()

def reconciled_summary(parts,whole):
    """Use an independently read summary structure, never invent empty cells.

    Only a shallow table's final row may be reconciled. Its nonempty content
    must agree exactly with a normal full-table read at the established width.
    """
    if len(parts)<2:return None
    def rows(text):return [r for r in text.split('<nl>') if r.strip()]
    def cells(row):return re.split(r'<(?:fcel|ecel|lcel|ucel|xcel)>',row)[1:]
    def values(row):return [re.sub(r'\s+','',c) for c in cells(row) if c.strip()]
    texts=[p['choices'][0]['message']['content'] for p in parts]
    if any(len(rows(t))!=1 for t in texts):return None
    widths=[len(cells(rows(t)[0])) for t in texts]
    if len(set(widths[:-1]))!=1 or widths[-1]>=widths[0]:return None
    if whole['choices'][0]['finish_reason'] not in {'stop','eos_token'} or whole.get('repetition_guard'):return None
    candidates=[r for r in rows(whole['choices'][0]['message']['content']) if len(cells(r))==widths[0] and values(r)==values(rows(texts[-1])[0])]
    if len(candidates)!=1:return None
    replaced={**whole,'choices':[{'index':0,'message':{'role':'assistant','content':candidates[0]+'<nl>'},'finish_reason':'stop'}]}
    return parts[:-1]+[replaced]

def combine(parts,metadata,height):
    complete=bool(parts) and metadata[-1]['y'][1]==height
    texts=[];widths=[]
    for part in parts:
        choice=part['choices'][0];text=choice['message']['content']
        complete=complete and choice['finish_reason'] in {'stop','eos_token'} and not part.get('repetition_guard',False)
        if '<fcel>' not in text and '<ecel>' not in text:complete=False
        rows=[r for r in text.split('<nl>') if r.strip()]
        widths.append(max((len(re.findall(r'<(?:fcel|ecel|lcel|ucel|xcel)>',r)) for r in rows),default=0))
        texts.append(text.rstrip()+('' if text.rstrip().endswith('<nl>') else '<nl>'))
    if len(set(widths))>1:complete=False
    usage_complete=all(p.get('token_usage_complete',True) and (p.get('usage') or {}).get('completion_tokens') is not None for p in parts)
    usage={key:sum((p.get('usage') or {}).get(key) or 0 for p in parts) for key in ['completion_tokens','prompt_tokens','total_tokens']} if usage_complete else {'completion_tokens':None}
    out={**parts[-1],'choices':[{'index':0,'message':{'role':'assistant','content':''.join(texts)},'finish_reason':'stop' if complete else 'length'}],
         'usage':usage,'token_usage_complete':usage_complete,'repetition_guard':any(p.get('repetition_guard',False) for p in parts),
         'received_chars':sum(len(p['choices'][0]['message']['content']) for p in parts),'assembled_chars':len(''.join(texts)),
         'table_bands':metadata,'table_band_columns':widths,'table_band_complete':bool(complete),'engine':'paddle-vl-table-bands'}
    return out
