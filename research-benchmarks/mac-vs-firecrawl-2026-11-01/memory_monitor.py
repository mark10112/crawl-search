import json,re,subprocess,sys,time
from pathlib import Path
import psutil
target=Path(sys.argv[1])
with target.open('a',buffering=1) as stream:
    while True:
        start=time.time();groups={'mlx':0,'ocr':0,'api':0};pids={}
        for proc in psutil.process_iter(['pid','name','cmdline','memory_info']):
            try:
                if 'python' not in (proc.info['name'] or '').lower():continue
                cmd=' '.join(proc.info['cmdline'] or [])
                group='mlx' if 'mlx_vlm.server' in cmd else 'ocr' if 'services/mac_ocr.py' in cmd else 'api' if 'local_research.server_api' in cmd else None
                if group:
                    rss=proc.info['memory_info'].rss;groups[group]+=rss;pids[str(proc.pid)]={'group':group,'rss':rss}
            except (psutil.AccessDenied,psutil.NoSuchProcess):continue
        vm=psutil.virtual_memory();swap=psutil.swap_memory()
        raw=subprocess.check_output(['vm_stat'],text=True);page=int(re.search(r'page size of (\d+)',raw)[1])
        counts={k.strip():int(v) for k,v in re.findall(r'^([^:\n]+):\s*(\d+)\.',raw,re.M)}
        stream.write(json.dumps({'time':start,'sample_seconds':round(time.time()-start,3),'rss':groups,'native_rss':sum(groups.values()),'pids':pids,
            'total_bytes':vm.total,'available_bytes':vm.available,'system_nonfree_bytes':vm.total-counts['Pages free']*page,
            'compressor_bytes':counts['Pages occupied by compressor']*page,'swap_used_bytes':swap.used,'swap_in_bytes':swap.sin,'swap_out_bytes':swap.sout})+'\n')
        time.sleep(max(.05,.5-(time.time()-start)))
