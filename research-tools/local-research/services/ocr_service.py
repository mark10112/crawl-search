"""Loopback Docker OCR service: persistent LightOn + bounded Rapid recognizer LRU."""
import base64
import hashlib
import io
import json
import os
import threading
import time
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image

REVISION='be7c41313c30e940fe5571de59e5fabc779e00c8'
STATE=Path('/cache/router-ocr-v1')
STATE.mkdir(exist_ok=True,parents=True)
RAPID_LANG={'en':'en','fr':'latin','de':'latin','es':'latin','it':'latin','pt':'latin','nl':'latin',
            'th':'th','zh':'ch','ja':'ch','ar':'arabic','hi':'devanagari'}
gpu_lock=threading.Lock()
cpu_lock=threading.Lock()
rapid_engines=OrderedDict()
model=None
processor=None


def lighton(image,max_tokens=1536):
    global model,processor
    import torch
    from transformers import LightOnOcrForConditionalGeneration,LightOnOcrProcessor
    with gpu_lock:
        if model is None:
            torch.set_num_threads(4)
            processor=LightOnOcrProcessor.from_pretrained('lightonai/LightOnOCR-2-1B',revision=REVISION)
            model,info=LightOnOcrForConditionalGeneration.from_pretrained('lightonai/LightOnOCR-2-1B',
                revision=REVISION,dtype=torch.bfloat16,device_map='cuda',attn_implementation='sdpa',output_loading_info=True)
            if info.get('missing_keys') or info.get('unexpected_keys') or info.get('mismatched_keys'):
                raise RuntimeError('LightOn checkpoint loading mismatch')
            model.eval()
        inputs=processor.apply_chat_template([{'role':'user','content':[{'type':'image','image':image}]}],
            add_generation_prompt=True,tokenize=True,return_dict=True,return_tensors='pt')
        inputs={k:v.to(device='cuda',dtype=torch.bfloat16) if v.is_floating_point() else v.to('cuda') for k,v in inputs.items()}
        with torch.inference_mode():
            ids=model.generate(**inputs,max_new_tokens=max_tokens,max_time=60,do_sample=False)
        torch.cuda.synchronize()
        generated=ids[0,inputs['input_ids'].shape[1]:]
        return processor.decode(generated,skip_special_tokens=True),len(generated)>=1536


def rapid(image,language):
    from rapidocr import RapidOCR,EngineType,ModelType,OCRVersion
    import numpy as np
    with cpu_lock:
        if language not in rapid_engines:
            if len(rapid_engines)>=3:
                rapid_engines.popitem(last=False)
            rapid_engines[language]=RapidOCR(params={
                'Global.model_root_dir':'/cache/rapid','Global.use_cls':False,'Global.log_level':'warning',
                'Det.engine_type':EngineType.ONNXRUNTIME,'Det.model_type':ModelType.MOBILE,'Det.ocr_version':OCRVersion.PPOCRV5,
                'Rec.engine_type':EngineType.ONNXRUNTIME,'Rec.lang_type':language,'Rec.model_type':ModelType.MOBILE,
                'Rec.ocr_version':OCRVersion.PPOCRV5,'EngineConfig.onnxruntime.intra_op_num_threads':4,
                'EngineConfig.onnxruntime.inter_op_num_threads':1})
        engine=rapid_engines.pop(language)
        rapid_engines[language]=engine
        result=engine(np.asarray(image)[:,:,::-1].copy())
        text='\n'.join(result.txts or [])
        scores=[float(v) for v in (result.scores if result.scores is not None else [])]
        return text,{'mean_confidence':sum(scores)/len(scores) if scores else 0,
                     'min_confidence':min(scores) if scores else 0,'lines':len(scores)}


def handle_ocr(body):
    start=time.perf_counter()
    image_bytes=base64.b64decode(body['image_base64'],validate=True)
    if len(image_bytes)>20*1024*1024:
        raise ValueError('Image exceeds 20 MiB')
    policy=body.get('policy','balanced')
    if policy not in {'balanced','quality'}:
        raise ValueError('policy must be balanced or quality')
    hint=(body.get('language_hint') or '').lower().split('-')[0]
    key=hashlib.sha256(image_bytes+json.dumps([policy,hint,REVISION,'gate-v1']).encode()).hexdigest()
    cache=body.get('cache',True)
    path=STATE/(key+'.json')
    if cache and path.exists():
        result=json.loads(path.read_text(encoding='utf-8'))
        result.update(cache_hit=True,elapsed_ms=round((time.perf_counter()-start)*1000,2))
        return result
    image=Image.open(io.BytesIO(image_bytes)).convert('RGB')
    if image.width*image.height>16000000:
        raise ValueError('Image exceeds 16 megapixels')
    route=[]
    text=''
    stats=None
    truncated=False
    if policy=='balanced' and hint in RAPID_LANG and not body.get('complex_layout',False):
        clock=time.perf_counter()
        text,stats=rapid(image,RAPID_LANG[hint])
        passed=(len(text.strip())>=80 and stats['mean_confidence']>=.95 and stats['min_confidence']>=.85
                and '\ufffd' not in text)
        route.append({'engine':'rapidocr','elapsed_ms':round((time.perf_counter()-clock)*1000,2),'quality_pass':passed,**stats})
        if not passed:
            text=''
    if not text:
        clock=time.perf_counter()
        text,truncated=lighton(image)
        route.append({'engine':'lighton','elapsed_ms':round((time.perf_counter()-clock)*1000,2)})
    result={'ok':len(text.strip())>=40 and not truncated,'text':text,'route':route,'cache_hit':False,
            'elapsed_ms':round((time.perf_counter()-start)*1000,2),'engine':route[-1]['engine'],
            'policy':policy,'language_hint':hint or None,'truncated':truncated,'revision':REVISION,
            'quality_warning':'Confidence checks do not prove factual or transcription accuracy.'}
    if cache and result['ok']:
        temp=path.with_suffix('.tmp')
        temp.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
        temp.replace(path)
    return result


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path!='/health':
            self.send_error(404);return
        self.reply({'ok':True,'model_loaded':model is not None,'rapid_loaded':list(rapid_engines),'revision':REVISION})
    def do_POST(self):
        if self.path!='/ocr':
            self.send_error(404);return
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length>28*1024*1024:raise ValueError('Payload too large')
            result=handle_ocr(json.loads(self.rfile.read(length)))
            self.reply(result)
        except Exception as exc:
            self.reply({'ok':False,'error':f'{type(exc).__name__}: {exc}'},500)
    def reply(self,value,status=200):
        payload=json.dumps(value,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)))
        self.end_headers();self.wfile.write(payload)
    def log_message(self,*args):pass


if __name__=='__main__':
    # Preload only weights; an explicit warmup request is excluded from benchmarks.
    if os.getenv('PRELOAD_LIGHTON','1')=='1':
        lighton(Image.new('RGB',(500,120),'white'),max_tokens=1)
    print('OCR service ready on :8091',flush=True)
    ThreadingHTTPServer(('0.0.0.0',8091),Handler).serve_forever()
