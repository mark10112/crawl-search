"""Replay old Census output: lossless text/table compaction, no inference or source edits."""
import json,sys,hashlib
from pathlib import Path
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'research-tools/local-research/services'))
from completion_checks import compact_markup
source=ROOT/'research-benchmarks/ocr-budget-round1-2026-11-01/results/telemetry.jsonl'
pages=[r['result']['text'] for r in map(json.loads,source.read_text(encoding='utf8').splitlines()) if r['kind']=='page' and r.get('variant')=='after' and r.get('mode')=='ocr' and r.get('id')=='us-census']
results=[]
for text in pages:
    compact=compact_markup(text)
    a=BeautifulSoup(text,'html.parser');b=BeautifulSoup(compact,'html.parser')
    assert a.get_text(' ')==b.get_text(' ')
    def cells(soup):return [(t.name,t.get('rowspan'),t.get('colspan'),t.get_text()) for t in soup.find_all(['table','tr','th','td'])]
    assert cells(a)==cells(b)
    results.append({'before_chars':len(text),'after_chars':len(compact),'plain_text_sha256':hashlib.sha256(a.get_text(' ').encode()).hexdigest(),'table_structure_and_text_unchanged':True})
assert len(results)==3
out={'source_telemetry_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'pages':results,'total_before':sum(r['before_chars'] for r in results),'total_after':sum(r['after_chars'] for r in results)}
(Path(__file__).parent/'compaction-replay.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
