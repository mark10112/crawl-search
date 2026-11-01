"""Validate reference separation, original controls and unchanged retained pixels."""
import hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageChops
from crop_geometry import dominant_bbox
P=Path(__file__).parent;OLD=P.parent/'ocr-backup-round5-2026-11-02'
inputs=json.loads((P/'inputs.json').read_text());refs=json.loads((P/'references.json').read_text(encoding='utf8'))
audit=json.loads((P/'reference-audit.json').read_text(encoding='utf8'));A=json.loads((P/'analysis.json').read_text(encoding='utf8'))
original=json.loads((P.parent/'real-history-2026-11-01/references.json').read_text(encoding='utf8'))
digest=hashlib.sha256(json.dumps(original,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
assert digest==inputs['reference_hash']==refs['reference_hash']==audit['reference_hash']=='72a37213b39a3a3dd1b4e344162d962b39c3c460fcad2bf2dfea105620301ac2'
assert refs==json.loads((OLD/'references.json').read_text(encoding='utf8'))
assert sum(r['primary_pixel_accuracy'] for r in audit['rows'])==6 and not audit['values_changed']
assert len(inputs['inputs'])==36
for case in inputs['inputs']:
    source=OLD/'inputs'/(case['source_id']+'.png');file=P/'inputs'/case['file']
    assert hashlib.sha256(file.read_bytes()).hexdigest()==case['sha256']
    assert hashlib.sha256(source.read_bytes()).hexdigest()==case['parent_sha256']
    parent=Image.open(source).convert('RGB');actual=Image.open(file).convert('RGB')
    if case['variant']=='original':assert source.read_bytes()==file.read_bytes()
    if case['variant'].startswith('tight'):assert dominant_bbox(parent)==case['source_local_bbox']
    pad=case['padding'];inner=actual.crop((pad,pad,actual.width-pad,actual.height-pad)) if pad else actual
    assert ImageChops.difference(inner,parent.crop(case['source_local_bbox'])).getbbox() is None
    if pad:
        arr=np.asarray(actual)
        assert pad==10 and all(np.all(strip==255) for strip in [arr[:pad],arr[-pad:],arr[:,:pad],arr[:,-pad:]])
count=0
for mode in ['vl','tesseract_best']:
    data=json.loads((P/'results'/(mode+'.json')).read_text(encoding='utf8'))
    old=json.loads((OLD/'results'/(mode+'.json')).read_text(encoding='utf8'))
    assert len(data['rows'])==144
    assert sorted((r['id'],r['repeat']) for r in data['rows'])==sorted((c['id'],n) for c in inputs['inputs'] for n in range(4))
    for row in data['rows']:
        assert row['input_sha256']==next(c['sha256'] for c in inputs['inputs'] if c['id']==row['id'])
        assert row['complete'] and row['seconds']>0 and row['ended_at']>=row['started_at']
        if mode=='tesseract_best':assert row['child_peak_rss_bytes']>0 and row['returncode']==0
        if row['variant']=='original' and row['repeat']>0:
            control=next(r for r in old['rows'] if r['id']==row['source_id'] and r['repeat']==row['repeat'])
            assert row['text']==control['text']
    samples=[json.loads(l) for l in (P/(mode+'-memory.jsonl')).read_text().splitlines()]
    assert len(samples)>30 and max(s['rss'] for s in samples)>0
    count+=len(data['rows'])
assert count==288
assert all(g['varying_outputs']==0 for s in A['summaries'] for g in s['groups'].values())
health=json.loads((P/'restored.json').read_text())['health']
assert health['commit']=='ac1b98ba313e49f0c9a4be57e382a083fa6f0f8b' and health['worker_alive'] and not health['draining'] and health['ocr_router']['ok']
out={'status':'passed','reference_hash':digest,'reference_values_changed':False,'image_confirmed_primary_cases':6,
     'ambiguous_scan_cases_reported_separately':3,'frozen_images':36,'pixel_identity_verified_images':36,
     'reader_observations':count,'original_controls_match_round5':True,'warm_repeats':3,
     'production_commit':health['commit'],'runtime_changes':False,
     'note':'Retained pixels unchanged, white border exact, all outputs kept. RSS excludes unreported Metal allocations. No per-case oracle selection or holdout claim.'}
(P/'validation.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf8');print(json.dumps(out,indent=2))
