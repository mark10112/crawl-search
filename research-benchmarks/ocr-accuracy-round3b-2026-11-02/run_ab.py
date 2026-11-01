"""Controlled sequential A/B; always restore the original production supervisors."""
import base64,hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent;BASE=Path.home()/'research-server'
WORK=BASE/'benchmarks/ocr-accuracy-round3b-2026-11-02';WORK.mkdir(parents=True,exist_ok=True)
assert not (WORK/'started.json').exists(),'Use a fresh run directory, do not overwrite evidence'
BEFORE=BASE/'experiments/ocr-accuracy-round3-before'
BEFORE_SHA='633aa9d32648e68813b33dfcdf10f54e8849a2a4'
PRODUCTION=BASE/'deployments/releases/ac1b98ba313e49f0c9a4be57e382a083fa6f0f8b'
PY=PRODUCTION/'research-tools/local-research/.venv/bin/python';OCR=BASE/'envs/ocr/bin/python'
MODEL=Path.home()/'.cache/huggingface/hub/models--PaddlePaddle--PaddleOCR-VL-1.6/snapshots/c5630abae1d940eafe0697512a0325494b02ab42'
domain=f'gui/{os.getuid()}';processes={};paused=False;ocr_stopped=False
def run(args,**kwargs):return subprocess.run([str(a) for a in args],check=True,**kwargs)
def write(path,data):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2));temp.replace(path)
def spawn(name,args,env):
    log=(WORK/(name+'.log')).open('ab')
    p=subprocess.Popen([str(a) for a in args],stdout=log,stderr=log,stdin=subprocess.DEVNULL,env=env,start_new_session=True);processes[name]=p;return p
def stop(name):
    p=processes.pop(name,None)
    if p and p.poll() is None:
        p.terminate()
        try:p.wait(timeout=15)
        except subprocess.TimeoutExpired:p.kill();p.wait()
def wait_ready(url,timeout=180):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        try:
            r=httpx.get(url,timeout=5)
            if r.status_code==200:return
        except httpx.HTTPError:pass
        time.sleep(.5)
    raise TimeoutError(url)
def restart_mlx():
    run(['launchctl','kickstart','-k',domain+'/local.crawl-search.mlx'])
    time.sleep(2);wait_ready('http://127.0.0.1:8111/v1/models')
def restore():
    for name in list(processes):stop(name)
    if paused:
        if ocr_stopped:
            plist=Path.home()/'Library/LaunchAgents/local.crawl-search.ocr.plist'
            run(['launchctl','bootstrap',domain,plist])
        wait_ready('http://127.0.0.1:8091/health')
        r=httpx.post('http://127.0.0.1:8768/maintenance',json={'action':'resume'},timeout=20);r.raise_for_status()
        run(['launchctl','bootstrap',domain,Path.home()/'Library/LaunchAgents/local.crawl-search.deploy.plist'])
        h=httpx.get('http://127.0.0.1:8768/health',timeout=20).json();assert not h['draining'] and h['worker_alive'] and h['ocr_router']['ok']
        write(WORK/'restored.json',{'time':time.time(),'health':h})
def interrupted(*args):raise KeyboardInterrupt('benchmark interrupted; restoring services')
signal.signal(signal.SIGTERM,interrupted)
candidate=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
write(WORK/'started.json',{'time':time.time(),'before_sha':BEFORE_SHA,'after_sha':candidate,'reader_sha':'matched-to-worker-per-variant','protocol':str(HERE/'METHOD.md')})
manifest=json.loads((ROOT/'research-benchmarks/real-history-2026-11-01/manifest.json').read_text())['cases']
assets=BASE/'releases/2026-11-01-ocr/research-benchmarks/real-history-2026-11-01/public-assets'
for case in manifest:assert hashlib.sha256((assets/case['filename']).read_bytes()).hexdigest()==case['sha256']
env={**os.environ,'PYTHONUNBUFFERED':'1','MAC_OCR_MODEL':str(MODEL),'PADDLEOCR_VL_MAX_NEW_TOKENS':'8192','PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK':'True',
    'LOCAL_RESEARCH_STATE':str(WORK/'reader'),'RESEARCH_JOBS_DIR':str(WORK/'jobs'),'LOCAL_RESEARCH_PORT':'8778',
    'LOCAL_RESEARCH_OCR_URL':'http://127.0.0.1:8091','LOCAL_RESEARCH_OCR_TIMEOUT':'480','RESEARCH_COMMIT':BEFORE_SHA,'RESEARCH_START_DRAINED':'0'}
try:
    run(['launchctl','bootout',domain+'/local.crawl-search.deploy'])
    paused=True
    r=httpx.post('http://127.0.0.1:8768/maintenance',json={'action':'drain'},timeout=20);r.raise_for_status()
    deadline=time.monotonic()+900
    while time.monotonic()<deadline:
        jobs=httpx.get('http://127.0.0.1:8768/health',timeout=20).json()['jobs']
        if not jobs.get('running',0) and not jobs.get('queued',0):break
        time.sleep(1)
    else:raise TimeoutError('Production jobs busy')
    run(['launchctl','bootout',domain+'/local.crawl-search.ocr']);ocr_stopped=True;time.sleep(1)
    spawn('memory',[OCR,HERE/'memory_monitor.py',WORK/'memory.jsonl'],env)
    with httpx.Client(base_url='http://127.0.0.1:8778',timeout=30) as client:
        for variant,source in [('after',ROOT)]:
            gateway_env={**env,'PYTHONPATH':str(source/'research-tools/local-research/src'),'RESEARCH_COMMIT':BEFORE_SHA if variant=='before' else candidate,'LOCAL_RESEARCH_STATE':str(WORK/variant/'reader'),'RESEARCH_JOBS_DIR':str(WORK/variant/'jobs')}
            spawn('gateway',[PY,'-m','local_research.server_api'],gateway_env);wait_ready('http://127.0.0.1:8778/health')
            uploads={}
            for case in manifest:
                r=client.post('/uploads',content=(assets/case['filename']).read_bytes());r.raise_for_status();uploads[case['id']]=r.json()['upload_id']
            restart_mlx()
            venv={**env,'MAC_OCR_STATE':str(WORK/variant/'ocr')}
            spawn('worker',[OCR,HERE/'observe_worker.py',source,WORK],venv);wait_ready('http://127.0.0.1:8091/health')
            write(WORK/'current.json',{'variant':variant,'mode':'warmup','id':'english'})
            png=(ROOT/'research-benchmarks/ocr-multilingual-2026-11-01/dataset/english.png').read_bytes()
            warm=httpx.post('http://127.0.0.1:8091/ocr',json={'image_base64':base64.b64encode(png).decode(),'cache':False},timeout=480).json()
            assert warm.get('ok') and '12,450.75' in warm.get('text',''),warm
            write(WORK/f'{variant}-warmup.json',warm)
            for mode in ['auto','ocr']:
                for case in manifest:
                    write(WORK/'current.json',{'variant':variant,'mode':mode,'id':case['id']})
                    request={'upload_id':uploads[case['id']],'mode':mode,'cache':False,'max_pages':3,'max_chars':40000,'ocr_policy':'quality' if mode=='ocr' else 'balanced'}
                    start=time.time();clock=time.perf_counter()
                    r=client.post('/jobs',json=request);r.raise_for_status();job=r.json()
                    while job['status'] in {'queued','running'}:
                        if time.perf_counter()-clock>1500:raise TimeoutError('Timed out; pending job retained')
                        time.sleep(.1);r=client.get('/jobs/'+job['id']);r.raise_for_status();job=r.json()
                    result=job['result'];assert result.get('content_sha256')==case['sha256']
                    row={'variant':variant,'mode':mode,'id':case['id'],'worker_sha':BEFORE_SHA if variant=='before' else candidate,
                        'reader_sha':BEFORE_SHA if variant=='before' else candidate,'started_at':start,'ended_at':time.time(),'elapsed_ms':round((time.perf_counter()-clock)*1000,2),'request':request,'raw':result}
                    out=WORK/'results';out.mkdir(exist_ok=True);write(out/f'{variant}-{mode}-{case["id"]}.json',row)
                    print(json.dumps({k:row[k] for k in ['variant','mode','id','elapsed_ms']}|{'ok':result.get('ok'),'error':result.get('error')},ensure_ascii=False),flush=True)
            stop('worker');stop('gateway')
    write(WORK/'completed.json',{'time':time.time()})
finally:restore()
