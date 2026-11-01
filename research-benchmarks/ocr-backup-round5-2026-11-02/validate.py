"""Audit source identity, complete repeated evidence and service restoration."""
import hashlib,json
from pathlib import Path
P=Path(__file__).parent
inputs=json.loads((P/'inputs.json').read_text());refs=json.loads((P/'references.json').read_text(encoding='utf8'))
A=json.loads((P/'analysis.json').read_text(encoding='utf8'))
original=json.loads((P.parent/'real-history-2026-11-01/references.json').read_text(encoding='utf8'))
digest=hashlib.sha256(json.dumps(original,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
assert digest==inputs['reference_hash']==refs['reference_hash']==A['reference_hash']=='72a37213b39a3a3dd1b4e344162d962b39c3c460fcad2bf2dfea105620301ac2'
assert len(inputs['inputs'])==len(refs['values'])==9
for case in inputs['inputs']:
    assert hashlib.sha256((P/'inputs'/case['file']).read_bytes()).hexdigest()==case['sha256']
    if case['group']=='census':
        assert (P/'inputs'/case['file']).read_bytes()==(P.parent/'ocr-row-round4-2026-11-02/crop-study'/case['file']).read_bytes()
assert inputs['inputs'][0]['sha256']=='7120aa4d5c51426815179501000d00a71730501697a87b970008d889e34376d4'
assert inputs['inputs'][4]['sha256']=='5441c8db5798afa21905e3d392a39fdc7a8a49cac9db19875271a8d15eae2b99'
count=0
for mode,folder in [('vl',P),('paddle_mobile',P),('tesseract_fast',P),('tesseract_best',P),('paddle_mobile_ocr',P/'supplement'),('tesseract_best_psm8',P/'wordmodes'),('tesseract_best_psm13',P/'wordmodes')]:
    data=json.loads((folder/'results'/(mode+'.json')).read_text(encoding='utf8'))
    assert len(data['rows'])==36
    assert sorted((r['id'],r['repeat']) for r in data['rows'])==sorted((c['id'],n) for c in inputs['inputs'] for n in range(4))
    assert all(r['input_sha256']==next(c['sha256'] for c in inputs['inputs'] if c['id']==r['id']) and r['seconds']>0 for r in data['rows'])
    for r in data['rows']:
        if mode.startswith('tesseract'):
            assert r['child_peak_rss_bytes']>0 and r['returncode']==0
        assert r['complete']
    sample=[json.loads(line) for line in (folder/(mode+'-memory.jsonl')).read_text().splitlines()]
    assert len(sample)>10 and max(s['rss'] for s in sample)>0
    count+=len(data['rows'])
for folder in [P,P/'supplement',P/'wordmodes']:
    assert json.loads((folder/'inputs.json').read_text())==inputs
    health=json.loads((folder/'restored.json').read_text())['health']
    assert health['commit']=='ac1b98ba313e49f0c9a4be57e382a083fa6f0f8b' and health['worker_alive'] and not health['draining'] and health['ocr_router']['ok']
assert count==252
assert all(g['varying_outputs']==0 for s in A['summaries'] for g in s['groups'].values())
best=next(s for s in A['summaries'] if s['mode']=='tesseract_best')
assert best['groups']['gazette']['correct_per_warm_pass']==[1,1,1]
assert best['groups']['census']['correct_per_warm_pass']==[1,1,1]
out={'status':'passed','reference_hash':digest,'unique_inputs':9,'observations':count,'configurations':7,
     'warm_repeats':3,'census_files_byte_identical':3,'old_gazette_request_hashes_verified':2,'reconstructed_gazette_crops':4,
     'restored_sessions':3,'production_commit':'ac1b98ba313e49f0c9a4be57e382a083fa6f0f8b','runtime_changes':False,
     'note':'RSS is not total Metal allocation; no holdout/generalization or automatic fallback claimed.'}
(P/'validation.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf8');print(json.dumps(out,indent=2))
