import hashlib,json,os,re,shutil,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=Path.home()/'research-server';work=Path(os.getenv('MAC_BENCH_WORK',str(BASE/'benchmarks/mac-vs-firecrawl-2026-11-01')))
work.mkdir(parents=True,exist_ok=True)
if (work/'processes.json').exists():raise RuntimeError('Benchmark already started; inspect existing processes first')
source=BASE/'releases/2026-11-01-ocr/research-benchmarks/real-history-2026-11-01/public-assets'
assets=work/'public-assets';assets.mkdir(exist_ok=True)
manifest=json.loads((ROOT/'research-benchmarks/real-history-2026-11-01/manifest.json').read_text())
for case in manifest['cases']:
    data=(source/case['filename']).read_bytes();assert hashlib.sha256(data).hexdigest()==case['sha256']
    (assets/case['filename']).write_bytes(data)
PY=ROOT/'research-tools/local-research/.venv/bin/python';OCR=BASE/'envs/ocr/bin/python';HERE=Path(__file__).parent;pids={}
def spawn(label,args,env=None):
    log=(work/(label+'.log')).open('ab')
    p=subprocess.Popen([str(a) for a in args],cwd=ROOT,stdout=log,stderr=log,stdin=subprocess.DEVNULL,start_new_session=True,env=env)
    pids[label]=p.pid;(work/'processes.json').write_text(json.dumps(pids,indent=2));return p
spawn('fixture',[PY,HERE/'serve.py',assets,work/'origin-requests.jsonl'])
spawn('memory',[OCR,HERE/'memory_monitor.py',work/'memory.jsonl'])
env={**os.environ,'LOCAL_RESEARCH_STATE':str(work/'reader-cache'),'RESEARCH_JOBS_DIR':str(work/'jobs'),
    'LOCAL_RESEARCH_PORT':'8778','LOCAL_RESEARCH_OCR_URL':'http://127.0.0.1:8091','LOCAL_RESEARCH_OCR_TIMEOUT':'480',
    'SEARXNG_URL':'http://127.0.0.1:8088','RESEARCH_COMMIT':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),
    'PYTHONUNBUFFERED':'1','CRAWL4AI_NO_CLOUD_NOTICE':'1'}
spawn('api',[PY,'-m','local_research.server_api'],env)
spawn('tunnel',['/opt/homebrew/bin/cloudflared','tunnel','--url','http://127.0.0.1:8877','--no-autoupdate','--protocol','http2'])
for _ in range(90):
    log=(work/'tunnel.log').read_text(errors='replace');match=re.search(r'https://[a-z0-9-]+\.trycloudflare\.com',log)
    if match:break
    time.sleep(.5)
else:raise RuntimeError('No temporary tunnel URL; inspect tunnel.log')
model={'revision':'c5630abae1d940eafe0697512a0325494b02ab42','model':'PaddlePaddle/PaddleOCR-VL-1.6','layout':'PP-DocLayoutV3','max_tokens':8192}
config={'base_url':match[0],'work':str(work),'pids':pids,'model':model,'commit':env['RESEARCH_COMMIT'],'started_at':time.time(),
    'ram_bytes':int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True)),
    'hardware':subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),
    'macos':subprocess.check_output(['sw_vers','-productVersion'],text=True).strip(),
    'reference_sha256':hashlib.sha256((ROOT/'research-benchmarks/real-history-2026-11-01/references.json').read_bytes()).hexdigest()}
(work/'config.json').write_text(json.dumps(config,indent=2));print(json.dumps(config),flush=True)
