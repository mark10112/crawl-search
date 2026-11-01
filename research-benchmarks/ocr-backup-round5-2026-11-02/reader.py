"""Read frozen images, with no access to expected values or reference files."""
import base64,hashlib,importlib.metadata,importlib.util,json,os,re,resource,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
mode=sys.argv[1];WORK=Path(sys.argv[2]);OUT=WORK/'results';OUT.mkdir(exist_ok=True)
inputs=json.loads((WORK/'inputs.json').read_text())['inputs']
rows=[];models={};setup={};start=time.perf_counter()
if mode=='vl':
    services=ROOT/'research-tools/local-research/services';sys.path.insert(0,str(services))
    spec=importlib.util.spec_from_file_location('original_worker',services/'mac_ocr.py');worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
    models={'revision':worker.REVISION,'max_tokens':8192,'prompt':'OCR:','backend':'MLX/Metal'}
    import httpx
    def read(file,language):
        request={'messages':[{'role':'user','content':[{'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(file.read_bytes()).decode()}},{'type':'text','text':'OCR:'}]}]}
        request,_=worker.recognition_request(request)
        response=worker.stream_recognition('/v1/chat/completions',request)
        if response.status_code!=200:raise RuntimeError('HTTP '+str(response.status_code))
        raw=response.json();choice=raw['choices'][0]
        return {'text':choice['message']['content'],'complete':choice['finish_reason'] in {'stop','eos_token'} and not raw.get('repetition_guard'),
                'finish_reason':choice['finish_reason'],'raw':raw}
    before=time.perf_counter();warm=read(ROOT/'research-benchmarks/ocr-multilingual-2026-11-01/dataset/english.png','eng')
    setup['warmup_seconds']=time.perf_counter()-before;setup['warmup']=warm
elif mode in ['paddle_mobile','paddle_mobile_ocr']:
    import numpy as np
    from PIL import Image
    from paddleocr import TextRecognition,PaddleOCR
    load_times={}
    for language,model in [('tha','th_PP-OCRv5_mobile_rec'),('eng','en_PP-OCRv5_mobile_rec')]:
        before=time.perf_counter()
        if mode=='paddle_mobile':
            models[language]=TextRecognition(model_name=model,model_dir=str(Path.home()/'.paddlex/official_models'/model),device='cpu',enable_mkldnn=False,cpu_threads=2)
        else:
            models[language]=PaddleOCR(text_detection_model_name='PP-OCRv5_mobile_det',text_recognition_model_name=model,
                use_doc_orientation_classify=False,use_doc_unwarping=False,use_textline_orientation=False,
                device='cpu',enable_mkldnn=False,cpu_threads=2,text_rec_score_thresh=0.0)
        load_times[language]=time.perf_counter()-before
    setup['model_constructor_seconds']=load_times
    def read(file,language):
        image=np.asarray(Image.open(file).convert('RGB'))[:,:,::-1].copy()
        results=list(models[language].predict(input=[image],**({'batch_size':1} if mode=='paddle_mobile' else {})))
        if len(results)!=1:raise RuntimeError('Unexpected recognition count')
        raw=results[0].json;raw=raw.get('res',raw)
        if mode=='paddle_mobile':return {'text':raw['rec_text'],'score':float(raw['rec_score']),'complete':True,'raw':raw}
        return {'text':' '.join(raw['rec_texts']),'scores':raw['rec_scores'],'complete':True,'raw':raw}
elif mode.startswith('tesseract_'):
    variant=mode.split('_')[1];folder=Path.home()/'research-server/models/tesseract-round5'/variant
    def read(file,language):
        psm=mode.split('_')[2].replace('psm','') if len(mode.split('_'))>2 else '7'
        command=['/usr/bin/time','-l','/opt/homebrew/bin/tesseract',str(file),'stdout','--tessdata-dir',str(folder),'-l',language,'--oem','1','--psm',psm]
        result=subprocess.run(command,capture_output=True,text=True,timeout=30)
        peak=re.search(r'(\d+)\s+maximum resident set size',result.stderr)
        return {'text':result.stdout.strip(),'complete':result.returncode==0,'returncode':result.returncode,
                'child_peak_rss_bytes':int(peak[1]) if peak else None,'stderr':result.stderr,'command':command}
else:raise ValueError(mode)
setup['startup_seconds']=time.perf_counter()-start
def save():
    payload={'mode':mode,'setup':setup,'rows':rows,'self_peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    # Package metadata does not require importing heavyweight model frameworks.
    versions={}
    for name in ['paddleocr','paddlex','paddlepaddle','mlx-vlm','pillow','numpy','psutil']:
        try:versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:pass
    payload['versions']=versions
    (OUT/(mode+'.json')).write_text(json.dumps(payload,ensure_ascii=False,indent=2))
save();print(json.dumps({'mode':mode,'ready':True,'startup_seconds':setup['startup_seconds']}),flush=True)
for repeat in range(4):  # First pass separately, then three measured warm passes.
    for case in inputs:
        file=WORK/'inputs'/case['file'];assert hashlib.sha256(file.read_bytes()).hexdigest()==case['sha256']
        begin=time.perf_counter()
        try:result=read(file,case['language'])
        except Exception as exc:result={'text':'','complete':False,'error':type(exc).__name__+': '+str(exc)}
        rows.append({'id':case['id'],'group':case['group'],'repeat':repeat,'input_sha256':case['sha256'],
                     'seconds':time.perf_counter()-begin,**result})
        save()
    print(json.dumps({'mode':mode,'repeat_finished':repeat,'observations':len(rows)}),flush=True)
