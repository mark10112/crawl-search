"""Validate raw observations and diagnostic pixel identity; no inference."""
import hashlib,json
from pathlib import Path
from PIL import Image,ImageChops
P=Path(__file__).parent
A=json.loads((P/'analysis.json').read_text(encoding='utf8'))
refs=json.loads((P.parent/'real-history-2026-11-01/references.json').read_text(encoding='utf8'))
digest=hashlib.sha256(json.dumps(refs,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
assert digest==A['reference_hash']=='72a37213b39a3a3dd1b4e344162d962b39c3c460fcad2bf2dfea105620301ac2'
manifest=json.loads((P.parent/'real-history-2026-11-01/manifest.json').read_text())
observations=list((P/'trials').glob('*/results/after-ocr-*.json'))
assert len(observations)==13
for file in observations:
    rec=json.loads(file.read_text(encoding='utf8'))
    assert not rec['request']['cache']
    assert rec['raw']['content_sha256']==next(c['sha256'] for c in manifest['cases'] if c['id']==rec['id'])
for ident,trial in [('thai-gazette','4g'),('us-preservation','4g'),('thai-royal','4b'),('us-census','4b')]:
    file=P/'results'/f'after-ocr-{ident}.json'
    assert file.read_bytes()==(P/'trials'/trial/'results'/file.name).read_bytes()
    rec=json.loads(file.read_text(encoding='utf8'))
    assert rec['raw']['ok'] and rec['raw']['output_complete'] and not rec['raw']['truncated']
    assert hashlib.sha256(file.read_bytes()).hexdigest()==next(d['raw_sha256'] for d in A['documents'] if d['variant']=='after' and d['id']==ident)
for variant,ident,correct in [('after','thai-gazette',0),('after','us-preservation',3)]:
    assert next(d['strict_rows'] for d in A['documents'] if (d['variant'],d['id'])==(variant,ident))==correct
study=json.loads((P/'crop-study/results.json').read_text(encoding='utf8'))
assert study['model_revision']=='c5630abae1d940eafe0697512a0325494b02ab42'
assert len(study['rows'])==26
for row in study['rows']:
    file=P/'crop-study'/(row['key']+'.png')
    assert hashlib.sha256(file.read_bytes()).hexdigest()==row['input_sha256']
    assert row['prompt']==('OCR:' if row['scope']=='cell' else 'Table Recognition:')
    if row['scope']=='whole':continue
    whole=next(r for r in study['rows'] if r['scope']=='whole' and r['page']==row['page'])
    x0,y0,_,_=whole['bbox'];b=row['bbox']
    expected=Image.open(P/'crop-study'/(whole['key']+'.png')).crop((b[0]-x0,b[1]-y0,b[2]-x0,b[3]-y0))
    actual=Image.open(file)
    assert expected.size==actual.size and ImageChops.difference(expected,actual).getbbox() is None
assert [A['crop_summary'][k]['correct'] for k in ['whole','row','cell']]==[11,14,17]
assert A['crop_summary']['cell']['previous_wrong_correct']==6
assert A['crop_summary']['cell']['control_correct']==11
for trial in ['4a','4b','4c','4d','4e','4f','4g']:
    health=json.loads((P/'trials'/trial/'restored.json').read_text())['health']
    assert health['commit']=='ac1b98ba313e49f0c9a4be57e382a083fa6f0f8b'
    assert health['worker_alive'] and not health['draining'] and health['ocr_router']['ok']
summary={'status':'passed','reference_hash':digest,'raw_document_observations':len(observations),
         'raw_crop_observations':26,'pixel_identical_crops_verified':24,'restored_trials':7,
         'target_candidate':'1a45c4d83bd22b418cb42be9ca92b0ec4ad933b0',
         'quality_gate_run':41337880956,'quality_gate':'success on Ubuntu and Windows',
         'note':'Final two target documents use 4g; Royal/Census use recorded 4b. No unified fresh four-document final-SHA claim. Gazette accuracy remains unresolved.'}
(P/'validation.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
print(json.dumps(summary,indent=2))
