"""Native Paddle layout + MLX recognition. Preserve each region's finish reason."""
import base64,hashlib,html,io,json,os,re,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import httpx
from PIL import Image
from completion_checks import completion_flags,compact_markup,excessive_repetition
from table_bands import is_table,request_image,bands,tile_request,combine
from row_geometry import index_rows,short_table_rows

REVISION='c5630abae1d940eafe0697512a0325494b02ab42'
STATE=Path(os.environ.get('MAC_OCR_STATE',str(Path.home()/'research-server/state/ocr')));STATE.mkdir(parents=True,exist_ok=True)
MODEL=os.environ['MAC_OCR_MODEL'];pipeline=None;lock=threading.Lock();generation_lock=threading.Lock();calls=[];recognition_profile='detail'
MAX_NEW_TOKENS=int(os.getenv('PADDLEOCR_VL_MAX_NEW_TOKENS','8192'))
if not 1<=MAX_NEW_TOKENS<=8192:raise ValueError('PADDLEOCR_VL_MAX_NEW_TOKENS must be between 1 and 8192')
REPETITION_PENALTY=float(os.getenv('MAC_OCR_REPETITION_PENALTY','1.0'))
if not 1<=REPETITION_PENALTY<=1.2:raise ValueError('MAC_OCR_REPETITION_PENALTY must be between 1 and 1.2')

def recognition_request(body):
    body=dict(body)
    requested=body.get('max_tokens') or body.get('max_completion_tokens')
    body.update(stream=False,temperature=0,max_tokens=min(int(requested or MAX_NEW_TOKENS),MAX_NEW_TOKENS),
                repetition_penalty=REPETITION_PENALTY,repetition_context_size=64)
    body.pop('max_completion_tokens',None);body['model']=MODEL
    return body,requested

def collect_stream(lines):
    """Reassemble SSE, cancelling consumption on the existing repetition rule.

    A guard is an incomplete result, never a synthetic normal finish. Token
    usage stays unknown when cancellation prevents the final usage packet.
    """
    text='';finish=None;usage=None;guard=False;chunks=0;checked=0;metadata={}
    for line in lines:
        if not line.startswith('data:'):continue
        data=line[5:].strip()
        if data=='[DONE]':break
        event=json.loads(data)
        metadata.update({k:event[k] for k in ['id','created','model'] if k in event})
        if event.get('error'):raise RuntimeError(str(event['error']))
        if event.get('usage'):usage=event['usage']
        for choice in event.get('choices',[]):
            text+=choice.get('delta',{}).get('content') or ''
            chunks+=1
            if choice.get('finish_reason') is not None:finish=choice['finish_reason']
        if len(text)-checked>=128 or finish is not None:
            checked=len(text)
            if excessive_repetition(text[-4096:]):guard=True;break
    if not guard and finish is None:raise RuntimeError('Recognition stream ended without a finish reason')
    return {'id':metadata.get('id','native-'+str(time.time_ns())),'created':metadata.get('created',int(time.time())),
            'model':metadata.get('model',MODEL),'object':'chat.completion',
            'choices':[{'index':0,'message':{'role':'assistant','content':text},'finish_reason':'length' if guard else finish}],
            'usage':usage or {'completion_tokens':None},'repetition_guard':guard,
            'token_usage_complete':usage is not None,'received_chunks':chunks,'received_chars':len(text)}

def stream_recognition(path,body):
    streaming={**body,'stream':True,'stream_options':{'include_usage':True}}
    with httpx.Client(timeout=240) as client:
        with client.stream('POST','http://127.0.0.1:8111'+path,json=streaming) as response:
            if response.status_code!=200:return httpx.Response(response.status_code,content=response.read())
            payload=collect_stream(response.iter_lines())
    return httpx.Response(200,json=payload)

def forward_recognition(path,body):
    # Paddle dispatches regions concurrently. Keep only one image request in
    # this MLX backend's continuous batch; isolated crop probes finish normally
    # where concurrent layout requests can run to the token limit.
    with generation_lock:
        image=request_image(body) if recognition_profile!='baseline' and is_table(body) else None
        intervals=(short_table_rows(image) or bands(image)) if image is not None else []
        if len(intervals)<=1:return stream_recognition(path,body)
        parts=[];metadata=[]
        for interval in intervals:
            request,source_hash=tile_request(body,image,interval)
            response=stream_recognition(path,request)
            if response.status_code!=200:return response
            payload=response.json();parts.append(payload)
            metadata.append({'y':list(interval),'width':image.width,'input_sha256':source_hash,
                'finish_reason':payload['choices'][0]['finish_reason'],'usage':payload.get('usage'),
                'repetition_guard':payload.get('repetition_guard',False)})
            if payload['choices'][0]['finish_reason'] not in {'stop','eos_token'}:break
        assembled=combine(parts,metadata,image.height)
        if not assembled['table_band_complete'] and all(p['choices'][0]['finish_reason'] in {'stop','eos_token'} for p in parts):
            # Inconsistent band structure is not accepted or padded into a
            # success. Obtain a new complete read of the original table crop.
            single=stream_recognition(path,body)
            if single.status_code!=200:return single
            payload=single.json()
            payload['table_attempts']=[{'strategy':'bands','complete':False,'bands':metadata,
                'columns':assembled['table_band_columns']},{'strategy':'single-high-detail',
                'finish_reason':payload['choices'][0]['finish_reason'],'usage':payload.get('usage')}]
            return httpx.Response(200,json=payload)
        return httpx.Response(200,json=assembled)

class Proxy(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            body=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))))
            body,requested=recognition_request(body)
            r=forward_recognition(self.path,body)
            if r.status_code==200:
                payload=r.json();calls.extend({'finish_reason':'repetition_guard' if payload.get('repetition_guard') else c.get('finish_reason'),'tokens':payload.get('usage',{}).get('completion_tokens'),
                    'requested_max_tokens':requested,'effective_max_tokens':body['max_tokens'],
                    'repetition_penalty':body['repetition_penalty'],'repetition_context_size':body['repetition_context_size'],
                    'serialized':True,'repetition_guard':payload.get('repetition_guard',False),
                    'token_usage_complete':payload.get('token_usage_complete',True),'received_chars':payload.get('received_chars'),
                    'table_bands':payload.get('table_bands'),'table_band_complete':payload.get('table_band_complete'),
                    'table_band_columns':payload.get('table_band_columns'),'table_attempts':payload.get('table_attempts')} for c in payload.get('choices',[]))
            self.send_response(r.status_code);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(r.content)
        except Exception as exc:
            self.send_response(502);self.end_headers();self.wfile.write(json.dumps({'error':str(exc)}).encode())
    def do_GET(self):
        r=httpx.get('http://127.0.0.1:8111'+self.path,timeout=15);self.send_response(r.status_code);self.end_headers();self.wfile.write(r.content)
    def log_message(self,*args):pass

def read_crop(image,bbox,prompt='OCR:'):
    buf=io.BytesIO();image.crop(tuple(bbox)).save(buf,format='PNG');data=buf.getvalue()
    body={'messages':[{'role':'user','content':[{'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(data).decode()}},{'type':'text','text':prompt}]}]}
    body,requested=recognition_request(body)
    response=forward_recognition('/v1/chat/completions',body)
    if response.status_code!=200:raise RuntimeError('Crop recognition HTTP '+str(response.status_code))
    payload=response.json()
    choice=payload['choices'][0]
    meta={'bbox':bbox,'input_sha256':hashlib.sha256(data).hexdigest(),'finish_reason':choice['finish_reason'],
          'tokens':(payload.get('usage') or {}).get('completion_tokens'),'usage':payload.get('usage'),
          'requested_max_tokens':requested,'effective_max_tokens':body['max_tokens'],
          'repetition_guard':payload.get('repetition_guard',False),'token_usage_complete':payload.get('token_usage_complete',True)}
    calls.append(meta)
    return {'text':choice['message']['content'].strip(),**meta}

def read_index(image,rows):
    attempts=[];output=[]
    for row in rows:
        part=read_crop(image,row['bbox'],prompt='Table Recognition:')
        raw_rows=[r for r in part['text'].split('<nl>') if r.strip()]
        cells=re.split(r'<(?:fcel|ecel|lcel|ucel|xcel)>',raw_rows[0])[1:] if len(raw_rows)==1 else []
        cells=[c.strip() for c in cells]
        complete=part['finish_reason'] in {'stop','eos_token'} and not part['repetition_guard']
        complete=complete and len(cells)==3 and bool(cells[1]) and all(re.fullmatch(r'\d{1,6}',cells[j]) for j in [0,2])
        attempts.append({'geometry':row,'recognition':part,'cells':cells,'complete':bool(complete)})
        if not complete:return None,attempts
        output.append('<tr>'+''.join('<td>'+html.escape(cell)+'</td>' for cell in cells)+'</tr>')
    return '<table>'+''.join(output)+'</table>',attempts

def ocr(body):
    global pipeline,recognition_profile
    data=base64.b64decode(body['image_base64'],validate=True)
    if len(data)>20*1024*1024:raise ValueError('Image exceeds 20 MiB')
    image=Image.open(io.BytesIO(data))
    if image.width*image.height>16000000:raise ValueError('Image exceeds 16 megapixels')
    policy=body.get('policy','balanced')
    if policy not in {'balanced','quality'}:raise ValueError('Invalid OCR policy')
    profile=body.get('recognition_profile','detail')
    if profile not in {'detail','baseline'}:raise ValueError('Invalid recognition profile')
    key=hashlib.sha256(data+json.dumps([REVISION,'layout-mlx-v10-contextual-index-rows',policy,MAX_NEW_TOKENS,REPETITION_PENALTY,64,profile]).encode()).hexdigest();cache=STATE/(key+'.json')
    with lock:
        recognition_profile=profile
        if body.get('cache',True) and cache.exists():
            result=json.loads(cache.read_text());result.update(cache_hit=True,elapsed_ms=0);return result
        if pipeline is None:
            from paddleocr import PaddleOCRVL
            pipeline=PaddleOCRVL(pipeline_version='v1.6',device='cpu',use_doc_orientation_classify=False,use_doc_unwarping=False,
                vl_rec_backend='mlx-vlm-server',vl_rec_server_url='http://127.0.0.1:8112/',vl_rec_api_model_name=MODEL)
        calls.clear();start=time.perf_counter();path=STATE/(key+'.png');image.convert('RGB').save(path)
        # Paddle's pipeline otherwise supplies 4096, overriding its model/env default.
        output=list(pipeline.predict(str(path),max_new_tokens=MAX_NEW_TOKENS))
        texts=[];regions=[]
        for result in output:
            markdown=result.markdown;texts.append(markdown.get('markdown_texts',''))
            detail=result.json
            if isinstance(detail,dict):regions.extend(detail.get('res',detail).get('parsing_res_list',[]))
        layout_text='\n\n'.join(texts);original_text=layout_text;row_attempts=[]
        detected=index_rows(image) if profile!='baseline' else []
        if detected:
            rebuilt,row_attempts=read_index(image,detected)
            if rebuilt is not None:
                # Keep headings/year labels outside the reconstructed row area.
                top=detected[0]['bbox'][1];bottom=detected[-1]['bbox'][3]
                outside=[r.get('block_content','') for r in regions if r.get('block_label')!='seal' and
                         (r['block_bbox'][3]<top or r['block_bbox'][1]>bottom)]
                original_text='\n\n'.join(outside+[rebuilt])
        flags=completion_flags(original_text,calls)
        if detected and (not row_attempts or not all(a['complete'] for a in row_attempts) or len(row_attempts)!=len(detected)):
            flags.append('Index row reconstruction incomplete')
        text=compact_markup(original_text)
        result={'ok':not flags,'text':text,'engine':'paddleocr-vl-1.6-mlx-layout','revision':REVISION,'cache_hit':False,
            'truncated':bool(flags),'policy':policy,'max_new_tokens':MAX_NEW_TOKENS,'repetition_penalty':REPETITION_PENALTY,
            'original_markup_chars':len(original_text),'recognition_profile':profile,'language_hint':body.get('language_hint'),'elapsed_ms':round((time.perf_counter()-start)*1000,2),
            'route':[{'engine':'paddle-layout+mlx','regions':len(regions),'generations':list(calls)}],
            'quality_flags':flags,'regions':regions,'index_rows':row_attempts,'original_layout_text':layout_text if detected else None,
            'quality_warning':'Completion checks are not proof of transcription accuracy.'}
        if flags:result['error']='; '.join(flags)
        if body.get('cache',True) and result['ok']:
            temp=cache.with_suffix('.tmp');temp.write_text(json.dumps(result,ensure_ascii=False));temp.replace(cache)
        return result

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path!='/health':self.send_error(404);return
        try:
            response=httpx.get('http://127.0.0.1:8111/v1/models',timeout=5)
            self.reply({'ok':response.status_code==200,'backend':'paddle-layout+mlx','pipeline_loaded':pipeline is not None,'revision':REVISION})
        except Exception as exc:self.reply({'ok':False,'error':str(exc)},503)
    def do_POST(self):
        if self.path!='/ocr':self.send_error(404);return
        try:
            size=int(self.headers.get('Content-Length',0))
            if size>28*1024*1024:raise ValueError('Payload too large')
            self.reply(ocr(json.loads(self.rfile.read(size))))
        except Exception as exc:self.reply({'ok':False,'error':f'{type(exc).__name__}: {exc}'},500)
    def reply(self,value,status=200):
        data=json.dumps(value,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def log_message(self,*args):pass
if __name__=='__main__':
    threading.Thread(target=ThreadingHTTPServer(('127.0.0.1',8112),Proxy).serve_forever,daemon=True).start()
    ThreadingHTTPServer(('127.0.0.1',8091),Handler).serve_forever()
