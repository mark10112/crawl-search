"""Native Paddle layout + MLX recognition. Preserve each region's finish reason."""
import base64,hashlib,io,json,os,re,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import httpx
from PIL import Image
from completion_checks import completion_flags

REVISION='c5630abae1d940eafe0697512a0325494b02ab42'
STATE=Path(os.environ.get('MAC_OCR_STATE',str(Path.home()/'research-server/state/ocr')));STATE.mkdir(parents=True,exist_ok=True)
MODEL=os.environ['MAC_OCR_MODEL'];pipeline=None;lock=threading.Lock();calls=[]

class Proxy(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            body=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))))
            body.update(stream=False,temperature=0,max_tokens=min(int(body.get('max_tokens') or body.get('max_completion_tokens') or 8192),8192))
            body.pop('max_completion_tokens',None);body['model']=MODEL
            r=httpx.post('http://127.0.0.1:8111'+self.path,json=body,timeout=240)
            if r.status_code==200:
                payload=r.json();calls.extend({'finish_reason':c.get('finish_reason'),'tokens':payload.get('usage',{}).get('completion_tokens')} for c in payload.get('choices',[]))
            self.send_response(r.status_code);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(r.content)
        except Exception as exc:
            self.send_response(502);self.end_headers();self.wfile.write(json.dumps({'error':str(exc)}).encode())
    def do_GET(self):
        r=httpx.get('http://127.0.0.1:8111'+self.path,timeout=15);self.send_response(r.status_code);self.end_headers();self.wfile.write(r.content)
    def log_message(self,*args):pass

def ocr(body):
    global pipeline
    data=base64.b64decode(body['image_base64'],validate=True)
    if len(data)>20*1024*1024:raise ValueError('Image exceeds 20 MiB')
    image=Image.open(io.BytesIO(data))
    if image.width*image.height>16000000:raise ValueError('Image exceeds 16 megapixels')
    policy=body.get('policy','balanced')
    if policy not in {'balanced','quality'}:raise ValueError('Invalid OCR policy')
    key=hashlib.sha256(data+json.dumps([REVISION,'layout-mlx-v1',policy]).encode()).hexdigest();cache=STATE/(key+'.json')
    with lock:
        if body.get('cache',True) and cache.exists():
            result=json.loads(cache.read_text());result.update(cache_hit=True,elapsed_ms=0);return result
        if pipeline is None:
            from paddleocr import PaddleOCRVL
            pipeline=PaddleOCRVL(pipeline_version='v1.6',device='cpu',use_doc_orientation_classify=False,use_doc_unwarping=False,
                vl_rec_backend='mlx-vlm-server',vl_rec_server_url='http://127.0.0.1:8112/',vl_rec_api_model_name=MODEL)
        calls.clear();start=time.perf_counter();path=STATE/(key+'.png');image.convert('RGB').save(path)
        output=list(pipeline.predict(str(path)))
        texts=[];regions=[]
        for result in output:
            markdown=result.markdown;texts.append(markdown.get('markdown_texts',''))
            detail=result.json
            if isinstance(detail,dict):regions.extend(detail.get('res',detail).get('parsing_res_list',[]))
        text='\n\n'.join(texts);flags=completion_flags(text,calls)
        result={'ok':not flags,'text':text,'engine':'paddleocr-vl-1.6-mlx-layout','revision':REVISION,'cache_hit':False,
            'truncated':bool(flags),'policy':policy,'language_hint':body.get('language_hint'),'elapsed_ms':round((time.perf_counter()-start)*1000,2),
            'route':[{'engine':'paddle-layout+mlx','regions':len(regions),'generations':list(calls)}],
            'quality_flags':flags,'regions':regions,'quality_warning':'Completion checks are not proof of transcription accuracy.'}
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
