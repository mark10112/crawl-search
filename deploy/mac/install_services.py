"""Install per-user launchd services; run on the Mac after Git checkout/dependencies."""
import json,os,plistlib,secrets,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HOME=Path.home();BASE=HOME/'research-server'
PKG=ROOT/'research-tools/local-research';PY=PKG/'.venv/bin/python';OCR=BASE/'envs/ocr/bin/python'
MODEL=HOME/'.cache/huggingface/hub/models--PaddlePaddle--PaddleOCR-VL-1.6/snapshots/c5630abae1d940eafe0697512a0325494b02ab42'
config=BASE/'config/searxng';config.mkdir(parents=True,exist_ok=True)
settings=config/'settings.yml'
if not settings.exists():
    settings.write_text('use_default_settings:\n  engines:\n    keep_only: [google, bing, duckduckgo, wikipedia]\nserver:\n  secret_key: '+secrets.token_hex(32)+'\n  limiter: false\n  image_proxy: false\nsearch:\n  formats: [html, json]\noutgoing:\n  request_timeout: 8.0\n')
docker='/usr/local/bin/docker'
subprocess.run([docker,'pull','searxng/searxng:latest'],check=True)
containers=subprocess.check_output([docker,'ps','-a','--format','{{.Names}}'],text=True).splitlines()
if 'crawl-search-searxng' not in containers:
    subprocess.run([docker,'run','-d','--name','crawl-search-searxng','--restart','unless-stopped','--cpus','2','--memory','1536m','--memory-swap','1536m',
        '-p','127.0.0.1:8088:8080','-v',f'{config}:/etc/searxng','searxng/searxng:latest'],check=True)
else:subprocess.run([docker,'start','crawl-search-searxng'],check=True)
logs=BASE/'logs';logs.mkdir(exist_ok=True)
state=BASE/'state';state.mkdir(exist_ok=True)
env={'PATH':'/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin','HF_HUB_DISABLE_XET':'1','PYTHONUNBUFFERED':'1','CRAWL4AI_NO_CLOUD_NOTICE':'1',
    'PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK':'True','LOCAL_RESEARCH_STATE':str(state/'reader'),'LOCAL_RESEARCH_OCR_URL':'http://127.0.0.1:8091',
    'LOCAL_RESEARCH_OCR_TIMEOUT':'480','SEARXNG_URL':'http://127.0.0.1:8088','RESEARCH_JOBS_DIR':str(state/'jobs'),
    'MAC_OCR_MODEL':str(MODEL),'RESEARCH_COMMIT':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()}
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
