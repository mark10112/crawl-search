"""Join immutable fresh baseline with follow-up after data, retaining timestamps."""
import hashlib,json,shutil
from pathlib import Path
P=Path(__file__).parent;old=P.parent/'ocr-accuracy-round3-2026-11-01/results';out=P/'results'
assert (out/'completed.json').exists() and (out/'restored.json').exists()
rows=[]
for src in sorted(old.glob('before-*-*.json')):
    raw=json.loads(src.read_text())
    if 'raw' not in raw:continue
    assert raw['variant']=='before' and raw['worker_sha']=='633aa9d32648e68813b33dfcdf10f54e8849a2a4'
    shutil.copyfile(src,out/src.name)
    rows.append({'file':src.name,'sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'started_at':raw['started_at'],'ended_at':raw['ended_at']})
assert len(rows)==8
for name in ['memory.jsonl','telemetry.jsonl']:
    target=out/name
    after=out/('after-only-'+name)
    if not after.exists():shutil.copyfile(target,after)
    oldrows=list(map(json.loads,(old/name).read_text(encoding='utf8').splitlines()))
    before=[r for r in oldrows if r.get('variant')=='before'] if name=='telemetry.jsonl' else [r for r in oldrows if min(b['started_at'] for b in rows)-3<=r['time']<=max(b['ended_at'] for b in rows)+1]
    both=sorted(before+list(map(json.loads,after.read_text(encoding='utf8').splitlines())),key=lambda r:r['time'])
    target.write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in both)+'\n',encoding='utf8')
(out/'baseline-provenance.json').write_text(json.dumps({'source':'../ocr-accuracy-round3-2026-11-01/results','note':'Same-turn fresh baseline, byte-identical document result files; combined telemetry/memory retain timestamps. No before inference in follow-up.','files':rows},indent=2))
print('8 baseline files copied byte-for-byte; original after-only captures preserved')
