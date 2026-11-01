import hashlib
import json
import math
import re
import statistics
import unicodedata
from functools import lru_cache
from pathlib import Path
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parent
cases={c['id']:c for c in json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))['cases']}

def normalize(text):
    text=BeautifulSoup(text,'html.parser').get_text(' ')
    text=re.sub(r'(?m)^\s*#{1,6}\s+','',text)
    return re.sub(r'\s+','',unicodedata.normalize('NFC',text.replace('**','').replace('```','').replace('\\_','_')))

@lru_cache(None)
def distance(a,b):
    previous=list(range(len(b)+1))
    for i,ca in enumerate(a,1):
        current=[i]
        for j,cb in enumerate(b,1):current.append(min(current[-1]+1,previous[j]+1,previous[j-1]+(ca!=cb)))
        previous=current
    return previous[-1]

rows=[]
for provider in ['local','local-quality','firecrawl']:
    for phase in ['off','prime','hit']:
        for ident,case in cases.items():
            path=ROOT/'results'/f'{provider}-{phase}-{ident}.json'
            if not path.exists():continue
            record=json.loads(path.read_text(encoding='utf-8'))
            raw=record['raw']
            text=raw.get('text','') if provider.startswith('local') else raw.get('markdown','')
            success=raw.get('ok',False) if provider.startswith('local') else bool(text) and not raw.get('error') and raw.get('metadata',{}).get('statusCode',200)<400
            reference=normalize(case['reference'])
            predicted=normalize(text)
            cer=distance(reference,predicted)/len(reference) if success else 1.0
            row={'provider':provider,'phase':phase,'id':ident,'kind':case['kind'],'ok':success,
                 'elapsed_ms':record['elapsed_ms'],'cer_pct':round(cer*100,4),'credits_used':record.get('credits_used'),
                 'cache_hit':raw.get('cache_hit') if provider.startswith('local') else raw.get('metadata',{}).get('cacheState')=='hit',
                 'cache_state_reported':raw.get('cache_hit') if provider.startswith('local') else raw.get('metadata',{}).get('cacheState'),
                 'reader':raw.get('reader'),'ocr_routes':raw.get('ocr_routes',[]),'text':text,
                 'local_hash_matches':raw.get('content_sha256')==case['sha256'] if provider.startswith('local') else None}
            rows.append(row)
summaries=[]
for provider in ['local','local-quality','firecrawl']:
    for phase in ['off','prime','hit']:
        for group in ['all','scanned-pdf','web-and-digital']:
            selected=[r for r in rows if r['provider']==provider and r['phase']==phase
                      and (group=='all' or (r['kind']=='scanned-pdf' if group=='scanned-pdf' else r['kind']!='scanned-pdf'))]
            if not selected:continue
            durations=sorted(r['elapsed_ms'] for r in selected)
            summaries.append({'provider':provider,'phase':phase,'group':group,'n':len(selected),
                'ok':sum(r['ok'] for r in selected),'cache_hits':sum(r['cache_hit'] for r in selected),
                'mean_cer_pct':round(statistics.mean(r['cer_pct'] for r in selected),4),
                'p50_ms':round(statistics.median(durations),2),'p95_ms':durations[math.ceil(len(durations)*.95)-1],
                'serial_total_ms':round(sum(durations),2),'credits_used':sum(r['credits_used'] or 0 for r in selected),
                'unknown_credit_records':sum(r['credits_used'] is None for r in selected)})
result={'summaries':summaries,'rows':rows,'cases':len(cases)}
(ROOT/'results/analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
lines=['# Paired retrieval benchmark','', '| Provider | Phase | Group | n | OK | Cache hits | CER % | p50 ms | p95 ms | Credits |', '|---|---|---|---:|---:|---:|---:|---:|---:|---:|']
for r in summaries:
    lines.append(f"| {r['provider']} | {r['phase']} | {r['group']} | {r['n']} | {r['ok']} | {r['cache_hits']} | {r['mean_cer_pct']} | {r['p50_ms']} | {r['p95_ms']} | {r['credits_used']} |")
lines+=['','| Document | Local off CER % | Firecrawl off CER % | Local off ms | Firecrawl off ms |','|---|---:|---:|---:|---:|']
for ident in cases:
    selected={r['provider']:r for r in rows if r['id']==ident and r['phase']=='off'}
    if 'local' in selected and 'firecrawl' in selected:
        a,b=selected['local'],selected['firecrawl']
        lines.append(f"| {ident} | {a['cer_pct']} | {b['cer_pct']} | {a['elapsed_ms']} | {b['elapsed_ms']} |")
(ROOT/'results/analysis.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps(summaries,ensure_ascii=False,indent=2))
