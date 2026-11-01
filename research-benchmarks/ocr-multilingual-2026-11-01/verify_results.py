import hashlib
import json
from functools import lru_cache
from pathlib import Path
from runner import normalize

root = Path('/work')
items = {i['id']:i for i in json.loads((root/'dataset/manifest.json').read_text(encoding='utf-8'))['items']}


@lru_cache(None)
def independent_distance(a,b):
    previous = list(range(len(b)+1))
    for i,ca in enumerate(a,1):
        current = [i]
        for j,cb in enumerate(b,1):
            current.append(min(current[-1]+1,previous[j]+1,previous[j-1]+(ca!=cb)))
        previous = current
    return previous[-1]


for item in items.values():
    assert hashlib.sha256((root/'dataset'/item['image']).read_bytes()).hexdigest()==item['sha256']
for name in ['rapid','paddle','lighton']:
    result = json.loads((root/'results'/(name+'.json')).read_text(encoding='utf-8'))
    assert not result.get('fatal_error'), name
    assert len(result['rows'])==39, name
    assert {(r['id'],r['repeat']) for r in result['rows']} == {(key,rep) for key in items for rep in range(3)}
    for row in result['rows']:
        assert row['ok'] and not row.get('error') and not row.get('truncated'), (name,row['id'])
        reference,prediction = normalize(items[row['id']]['reference']),normalize(row['text'])
        assert independent_distance(reference,prediction)==row['edits'], (name,row['id'])
        assert abs(row['cer']-row['edits']/len(reference))<1e-12
    print(name+': 39 complete rows, image hashes and independent CER verified')
lighton = json.loads((root/'results/lighton.json').read_text(encoding='utf-8'))
assert lighton['metadata']['model_class']=='LightOnOcrForConditionalGeneration'
for path in ['results/lighton.json','results/paddle-loading-audit.json']:
    result = json.loads((root/path).read_text(encoding='utf-8'))
    assert not result.get('fatal_error')
    info = result['metadata']['loading_info']
    assert not info.get('missing_keys') and not info.get('unexpected_keys') and not info.get('mismatched_keys')
paddle = json.loads((root/'results/paddle.json').read_text(encoding='utf-8'))
audit = json.loads((root/'results/paddle-loading-audit.json').read_text(encoding='utf-8'))
assert paddle['metadata']['revision']==audit['metadata']['revision']
print('VLM checkpoint loading audits verified; no missing/unexpected/mismatched weights')
