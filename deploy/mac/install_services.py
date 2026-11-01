"""Install per-user launchd services; run on the Mac after Git checkout/dependencies."""
import json,os,plistlib,secrets,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HOME=Path.home();BASE=HOME/'research-server'
os.environ['PATH']='/opt/homebrew/bin:/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:/usr/bin:/bin:/usr/sbin:/sbin'
PKG=ROOT/'research-tools/local-research';PY=PKG/'.venv/bin/python';OCR=BASE/'envs/ocr/bin/python'
MODEL=HOME/'.cache/huggingface/hub/models--PaddlePaddle--PaddleOCR-VL-1.6/snapshots/c5630abae1d940eafe0697512a0325494b02ab42'
config=BASE/'config/searxng';config.mkdir(parents=True,exist_ok=True)
settings=config/'settings.yml'
if not settings.exists():
    settings.write_text('use_default_settings:\n  engines:\n    keep_only: [google, bing, duckduckgo, wikipedia]\nengines:\n  - name: google\n    disabled: false\n  - name: bing\n    disabled: false\nserver:\n  secret_key: '+secrets.token_hex(32)+'\n  limiter: false\n  image_proxy: false\nsearch:\n  formats: [html, json]\noutgoing:\n  request_timeout: 8.0\n')
docker='/usr/local/bin/docker'
image='searxng/searxng@sha256:f4aa660c54d062dedb268be84e821ea24e39f48c7a496af8dd02cc9eedb93847'
subprocess.run([docker,'pull',image],check=True)
containers=subprocess.check_output([docker,'ps','-a','--format','{{.Names}}'],text=True).splitlines()
if 'crawl-search-searxng' not in containers:
    subprocess.run([docker,'run','-d','--name','crawl-search-searxng','--restart','unless-stopped','--cpus','2','--memory','1536m','--memory-swap','1536m',
        '-p','127.0.0.1:8088:8080','-v',f'{config}:/etc/searxng',image],check=True)
else:subprocess.run([docker,'start','crawl-search-searxng'],check=True)
logs=BASE/'logs';logs.mkdir(exist_ok=True)
state=BASE/'state';state.mkdir(exist_ok=True);os.chmod(state,0o700)
env={'PATH':'/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin','HF_HUB_DISABLE_XET':'1','PYTHONUNBUFFERED':'1','CRAWL4AI_NO_CLOUD_NOTICE':'1',
    'PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK':'True','LOCAL_RESEARCH_STATE':str(state/'reader'),'LOCAL_RESEARCH_OCR_URL':'http://127.0.0.1:8091',
    'LOCAL_RESEARCH_OCR_TIMEOUT':'480','SEARXNG_URL':'http://127.0.0.1:8088','RESEARCH_JOBS_DIR':str(state/'jobs'),
    'MAC_OCR_MODEL':str(MODEL),'PADDLEOCR_VL_MAX_NEW_TOKENS':'8192','RESEARCH_COMMIT':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()}
agents=HOME/'Library/LaunchAgents';agents.mkdir(exist_ok=True)
services={
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
    subprocess.run(['launchctl','bootstrap',domain,str(path)],check=True)
print(json.dumps({'services':list(services),'commit':env['RESEARCH_COMMIT'],'state':str(state)}))
