"""Sequential isolated reader comparison, restoring every production service."""
import json,os,re,signal,subprocess,sys,threading,time
from pathlib import Path
import httpx,psutil
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
BASE=Path.home()/'research-server';WORK=Path(sys.argv[1]) if len(sys.argv)>1 else BASE/'benchmarks/ocr-crop-round6-2026-11-02'
MODES=os.getenv('BACKUP_MODES','vl,tesseract_best').split(',')
OCR=BASE/'envs/ocr/bin/python';domain=f'gui/{os.getuid()}'
MODEL=Path.home()/'.cache/huggingface/hub/models--PaddlePaddle--PaddleOCR-VL-1.6/snapshots/c5630abae1d940eafe0697512a0325494b02ab42'
assert (WORK/'inputs.json').exists() and not (WORK/'started.json').exists()
def write(name,data):(WORK/name).write_text(json.dumps(data,indent=2))
def command(args):return subprocess.run([str(a) for a in args],check=True)
def ready(url,seconds=180):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        try:
            if httpx.get(url,timeout=3).status_code==200:return
        except httpx.HTTPError:pass
        time.sleep(.25)
    raise TimeoutError(url)
def interrupted(*args):raise KeyboardInterrupt('Stopped; restoring production')
signal.signal(signal.SIGTERM,interrupted)
paused=False;ocr_down=False;mlx_down=False;active=None;monitor_stop=None;monitor_thread=None
env={**os.environ,'PYTHONUNBUFFERED':'1','MAC_OCR_MODEL':str(MODEL),'MAC_OCR_STATE':str(WORK/'vl-state'),
     'PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK':'True','OMP_NUM_THREADS':'2','OMP_THREAD_LIMIT':'2','OPENBLAS_NUM_THREADS':'2','MKL_NUM_THREADS':'2'}
def monitor(process,mode,stop):
    with (WORK/(mode+'-memory.jsonl')).open('a',buffering=1) as stream:
        while not stop.is_set():
            pids={}
            try:
                main=psutil.Process(process.pid)
                for p in [main]+main.children(recursive=True):pids[p.pid]=p
            except psutil.Error:pass
            if mode=='vl':
                for p in psutil.process_iter(['cmdline']):
                    try:
                        if 'mlx_vlm.server' in ' '.join(p.info['cmdline'] or []):pids[p.pid]=p
                    except psutil.Error:pass
            rss={}
            for pid,p in pids.items():
                try:rss[str(pid)]=p.memory_info().rss
                except psutil.Error:pass
            vm=psutil.virtual_memory();swap=psutil.swap_memory()
            stream.write(json.dumps({'time':time.time(),'rss':sum(rss.values()),'pids':rss,'available':vm.available,
                                     'swap_used':swap.used,'rss_includes_metal_allocation':False})+'\n')
            stop.wait(.02)
try:
    command(['launchctl','bootout',domain+'/local.crawl-search.deploy']);paused=True
    response=httpx.post('http://127.0.0.1:8768/maintenance',json={'action':'drain'},timeout=15);response.raise_for_status()
    deadline=time.monotonic()+300
    while True:
        health=httpx.get('http://127.0.0.1:8768/health',timeout=10).json()
        if not health['jobs'].get('running',0) and not health['jobs'].get('queued',0):break
        if time.monotonic()>deadline:raise TimeoutError('Production jobs still busy')
        time.sleep(.5)
    command(['launchctl','bootout',domain+'/local.crawl-search.ocr']);ocr_down=True
    before=time.perf_counter();command(['launchctl','kickstart','-k',domain+'/local.crawl-search.mlx']);ready('http://127.0.0.1:8111/v1/models')
    write('started.json',{'time':time.time(),'candidate':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),
                          'mlx_restart_to_ready_seconds':time.perf_counter()-before,'model_order':MODES,
                          'note':'One reader at a time; CPU readers run with production MLX unloaded. Model/file OS caches not flushed. Three warm passes after first pass.'})
    for mode in MODES:
        if mode!='vl' and not mlx_down:
            command(['launchctl','bootout',domain+'/local.crawl-search.mlx']);mlx_down=True
            time.sleep(1)
            for p in psutil.process_iter(['cmdline']):
                assert 'mlx_vlm.server' not in ' '.join(p.info['cmdline'] or []),'Production model still running during CPU comparison'
        log=(WORK/(mode+'.log')).open('ab')
        active=subprocess.Popen([str(OCR),str(HERE/'reader.py'),mode,str(WORK)],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log)
        monitor_stop=threading.Event();monitor_thread=threading.Thread(target=monitor,args=(active,mode,monitor_stop));monitor_thread.start()
        try:code=active.wait(timeout=600)
        except subprocess.TimeoutExpired:
            active.terminate();code=active.wait(timeout=15)
            write(mode+'-timeout.json',{'error':'Timed out after 600 seconds','code':code})
        finally:monitor_stop.set();monitor_thread.join();log.close()
        active=None
        print(json.dumps({'mode':mode,'exit_code':code}),flush=True)
        if code:write(mode+'-failure.json',{'exit_code':code,'note':'Retain partial results and log; not a successful benchmark.'})
    write('completed.json',{'time':time.time()})
finally:
    if active and active.poll() is None:
        active.terminate()
        try:active.wait(timeout=15)
        except subprocess.TimeoutExpired:active.kill();active.wait()
    if monitor_stop:monitor_stop.set()
    if monitor_thread:monitor_thread.join(timeout=5)
    if mlx_down:command(['launchctl','bootstrap',domain,Path.home()/'Library/LaunchAgents/local.crawl-search.mlx.plist'])
    if paused:
        ready('http://127.0.0.1:8111/v1/models')
        if ocr_down:command(['launchctl','bootstrap',domain,Path.home()/'Library/LaunchAgents/local.crawl-search.ocr.plist'])
        ready('http://127.0.0.1:8091/health')
        response=httpx.post('http://127.0.0.1:8768/maintenance',json={'action':'resume'},timeout=15);response.raise_for_status()
        command(['launchctl','bootstrap',domain,Path.home()/'Library/LaunchAgents/local.crawl-search.deploy.plist'])
        health=httpx.get('http://127.0.0.1:8768/health',timeout=10).json()
        assert not health['draining'] and health['worker_alive'] and health['ocr_router']['ok']
        write('restored.json',{'time':time.time(),'health':health})
