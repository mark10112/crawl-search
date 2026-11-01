"""Install per-user launchd services; run on the Mac after Git checkout/dependencies."""
import json,os,plistlib,secrets,subprocess,time
from pathlib import Path
ROOT=Path(os.getenv('RESEARCH_RELEASE_ROOT',str(Path(__file__).resolve().parents[2]))).resolve();HOME=Path.home();BASE=HOME/'research-server'
os.environ['PATH']='/opt/homebrew/bin:/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:/usr/bin:/bin:/usr/sbin:/sbin'
PKG=ROOT/'research-tools/local-research';PY=PKG/'.venv/bin/python';OCR=Path(os.getenv('RESEARCH_OCR_PYTHON',str(BASE/'envs/ocr/bin/python')))
MODEL=HOME/'.cache/huggingface/hub/models--PaddlePaddle--PaddleOCR-VL-1.6/snapshots/c5630abae1d940eafe0697512a0325494b02ab42'
config=BASE/'config/searxng';config.mkdir(parents=True,exist_ok=True)
settings=config/'settings.yml'
# PyYAML belongs to the OCR environment, not the lightweight reader environment.
# Preserve the existing server secret when updating the managed engine selection.
engine_names=['brave','duckduckgo','yahoo','mwmbl','wikipedia']
configure="""
import json,sys,yaml,secrets
from pathlib import Path
p=Path(sys.argv[1]);names=json.loads(sys.argv[2])
s=yaml.safe_load(p.read_text()) if p.exists() else {}
s=s or {}
s['use_default_settings']={'engines':{'keep_only':names}}
s['engines']=[{'name':n,'disabled':False} for n in names]
server=s.setdefault('server',{});server.setdefault('secret_key',secrets.token_hex(32))
server.update(limiter=False,image_proxy=False)
s.setdefault('search',{})['formats']=['html','json']
s.setdefault('outgoing',{})['request_timeout']=8.0
p.write_text(yaml.safe_dump(s));p.chmod(0o600)
"""
subprocess.run([str(OCR),'-c',configure,str(settings),json.dumps(engine_names)],check=True)
docker='/usr/local/bin/docker'
image='searxng/searxng@sha256:f4aa660c54d062dedb268be84e821ea24e39f48c7a496af8dd02cc9eedb93847'
if os.getenv('RESEARCH_USE_LOCAL_IMAGE')=='1':
    subprocess.run([docker,'image','inspect',image],check=True,stdout=subprocess.DEVNULL,timeout=30)
else:subprocess.run([docker,'pull',image],check=True,timeout=180)
containers=subprocess.check_output([docker,'ps','-a','--format','{{.Names}}'],text=True,timeout=30).splitlines()
if 'crawl-search-searxng' not in containers:
    subprocess.run([docker,'run','-d','--name','crawl-search-searxng','--restart','unless-stopped','--cpus','2','--memory','1536m','--memory-swap','1536m',
        '-p','127.0.0.1:8088:8080','-v',f'{config}:/etc/searxng',image],check=True,timeout=60)
else:
    actual=subprocess.check_output([docker,'inspect','--format','{{.Image}}','crawl-search-searxng'],text=True,timeout=30).strip()
    expected=subprocess.check_output([docker,'image','inspect','--format','{{.Id}}',image],text=True,timeout=30).strip()
    if actual!=expected:raise RuntimeError('Existing search container uses a different image; migrate it explicitly')
    subprocess.run([docker,'restart','crawl-search-searxng'],check=True,timeout=60)
logs=BASE/'logs';logs.mkdir(exist_ok=True)
state=BASE/'state';state.mkdir(exist_ok=True);os.chmod(state,0o700)
env={'PATH':'/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin','HF_HUB_DISABLE_XET':'1','PYTHONUNBUFFERED':'1','CRAWL4AI_NO_CLOUD_NOTICE':'1',
    'PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK':'True','LOCAL_RESEARCH_STATE':str(state/'reader'),'LOCAL_RESEARCH_OCR_URL':'http://127.0.0.1:8091',
    'LOCAL_RESEARCH_OCR_TIMEOUT':'480','SEARXNG_URL':'http://127.0.0.1:8088','RESEARCH_JOBS_DIR':str(state/'jobs'),
    'MAC_OCR_MODEL':str(MODEL),'PADDLEOCR_VL_MAX_NEW_TOKENS':'8192','RESEARCH_COMMIT':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()}
env.update(RESEARCH_START_DRAINED=os.getenv('RESEARCH_START_DRAINED','0'),RESEARCH_DEPLOY_STATUS_FILE=str(BASE/'deployments/status.json'),RESEARCH_DEPLOY_STATE_FILE=str(BASE/'deployments/state.json'))
agents=HOME/'Library/LaunchAgents';agents.mkdir(exist_ok=True)
services={
    'search':[str(PY),str(ROOT/'deploy/mac/search_service.py')],
    'mlx':[str(OCR),'-m','mlx_vlm.server','--host','127.0.0.1','--port','8111','--model',str(MODEL)],
    'ocr':[str(OCR),str(PKG/'services/mac_ocr.py')],
    'api':[str(PY),'-m','local_research.server_api']}
for name,args in services.items():
    label='local.crawl-search.'+name;path=agents/(label+'.plist')
    spec={'Label':label,'ProgramArguments':['/usr/bin/caffeinate','-i']+args,'WorkingDirectory':str(PKG),'EnvironmentVariables':env,
        'RunAtLoad':True,'KeepAlive':True,'ThrottleInterval':10,'StandardOutPath':str(logs/(name+'.log')),'StandardErrorPath':str(logs/(name+'.err.log'))}
    path.write_bytes(plistlib.dumps(spec));os.chmod(path,0o600)
    domain=f'gui/{os.getuid()}'
    subprocess.run(['launchctl','bootout',domain+'/'+label],capture_output=True)
    # bootout returns before the old service is fully reaped; wait before re-registering.
    for attempt in range(20):
        if subprocess.run(['launchctl','print',domain+'/'+label],capture_output=True).returncode!=0:break
        time.sleep(.25)
    for attempt in range(5):
        registered=subprocess.run(['launchctl','bootstrap',domain,str(path)],capture_output=True)
        if registered.returncode==0:break
        if attempt==4:raise RuntimeError(registered.stderr.decode())
        time.sleep(1)
print(json.dumps({'services':list(services),'commit':env['RESEARCH_COMMIT'],'state':str(state)}))
