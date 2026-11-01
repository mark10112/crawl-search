"""Score unchanged source-image references; separate rejection from accepted-output CER."""
import hashlib,json,re,statistics,sys,unicodedata
from functools import lru_cache
from pathlib import Path
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'.deps'))
import edlib

ref_path=ROOT.parent/'real-history-2026-11-01/references.json'
refs=json.loads(ref_path.read_text(encoding='utf-8'))
canonical=hashlib.sha256(json.dumps(refs,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
assert canonical==json.loads((ROOT/'reference-lock.json').read_text())['canonical_json_sha256']
manifest=json.loads((ROOT.parent/'real-history-2026-11-01/manifest.json').read_text())

def normalize(text):
    text=BeautifulSoup(text,'html.parser').get_text(' ')
    text=unicodedata.normalize('NFC',text).translate(str.maketrans({'“':'"','”':'"','‘':"'",'’':"'",'—':'-','–':'-'}))
    text=re.sub(r'[.·_\-]{3,}','',text)
    return re.sub(r'[\s#*`|\\]','',text)
def table_norm(text):
    text=normalize(text).lower()
    text=''.join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in text)
    return ''.join(c for c in text if c.isalnum() or unicodedata.category(c).startswith('M'))
@lru_cache(maxsize=2000)
def align(expected,text):
    if not text:return 1.0,''
    result=edlib.align(expected,text,mode='HW',task='locations');a,b=result['locations'][0]
    return result['editDistance']/len(expected),text[a:b+1]

samples=[]
memory_file=ROOT/'results/memory.jsonl'
if memory_file.exists():samples=[json.loads(l) for l in memory_file.read_text().splitlines() if l.strip()]
def profile(start,end):
    if not samples:return None
    inside=[s for s in samples if start<=s['time']<=end]
    before=[s for s in samples if start-2<=s['time']<start]
    selected=list(inside)
    if not selected:
        prior=[s for s in samples if s['time']<start];later=[s for s in samples if s['time']>end]
        selected=([prior[-1]] if prior else [])+([later[0]] if later else [])
    if not selected:return None
    baseline=statistics.median(s['native_rss'] for s in before) if before else selected[0]['native_rss']
    return {'in_call_samples':len(inside),'uses_bracketing_samples':not bool(inside),
        'native_rss_baseline':baseline,'native_rss_peak':max(s['native_rss'] for s in selected),
        'native_rss_peak_delta':max(s['native_rss'] for s in selected)-baseline,
        'system_nonfree_peak':max(s['system_nonfree_bytes'] for s in selected),
        'compressor_peak':max(s['compressor_bytes'] for s in selected),'available_min':min(s['available_bytes'] for s in selected),
        'swap_used_peak':max(s['swap_used_bytes'] for s in selected),
        'swap_in_delta':selected[-1]['swap_in_bytes']-selected[0]['swap_in_bytes'],
        'swap_out_delta':selected[-1]['swap_out_bytes']-selected[0]['swap_out_bytes']}

rows=[];details=[]
for file in sorted((ROOT/'results').glob('*.json')):
    if not file.name.startswith(('mac-off-','mac-prime-','mac-hit-','mac-forced-quality-off-','firecrawl-off-','firecrawl-prime-','firecrawl-hit-')):continue
    rec=json.loads(file.read_text(encoding='utf-8'));raw=rec['raw'];local=rec['provider'].startswith('mac')
    text=raw.get('text','') if local else raw.get('markdown','');clean=normalize(text)
    ok=bool(raw.get('ok')) if local else bool(text) and not raw.get('error') and not rec.get('is_tool_error') and raw.get('metadata',{}).get('statusCode',200)<400
    anchors=[]
    for ref in refs['anchors']:
        if ref['document']!=rec['id']:continue
        cer,pred=align(normalize(ref['text']),clean)
        anchors.append({'id':ref['id'],'page':ref['page'],'expected':normalize(ref['text']),'aligned_prediction':pred,
            'accepted_cer_pct':round(cer*100,3) if ok else None,'delivery_penalty_error_pct':round(cer*100,3) if ok else 100,
            'present':bool(ok and cer<=.2)})
    table_rows=[];flat=table_norm(text)
    for ref in refs['table_rows']:
        if ref['document']==rec['id']:
            table_rows.append({**ref,'correct':bool(ok and table_norm(ref['label']+''.join(ref['values'])) in flat)})
    case=next(c for c in manifest['cases'] if c['id']==rec['id'])
    row={'provider':rec['provider'],'phase':rec['phase'],'id':rec['id'],'ok':bool(ok),'elapsed_ms':rec['elapsed_ms'],
        'cache_hit':raw.get('cache_hit',False) if local else raw.get('metadata',{}).get('cacheState')=='hit',
        'credits_reported':rec.get('credits_used'),'reader':raw.get('reader'),'chars':len(text),'error':raw.get('error'),
        'accepted_cer_pct':round(statistics.mean(a['accepted_cer_pct'] for a in anchors),3) if ok else None,
        'delivery_penalty_error_pct':round(statistics.mean(a['delivery_penalty_error_pct'] for a in anchors),3),
        'anchors_present':sum(a['present'] for a in anchors),'anchors_total':len(anchors),
        'table_correct':sum(a['correct'] for a in table_rows),'table_total':len(table_rows),
        'hash_matches':raw.get('content_sha256')==case['sha256'] if local else None,
        'ocr_page_cache_hits':sum(bool(r.get('cache_hit')) for r in raw.get('ocr_routes',[])),
        'profile':profile(rec['started_at'],rec['ended_at']) if local else None}
    rows.append(row);details.append({'file':file.name,'anchors':anchors,'tables':table_rows})
summaries=[]
for provider in ['mac','firecrawl','mac-forced-quality']:
    for phase in ['off','prime','hit']:
        group=[r for r in rows if r['provider']==provider and r['phase']==phase]
        if not group:continue
        accepted=[r for r in group if r['ok']];profiles=[r['profile'] for r in group if r['profile']]
        summaries.append({'provider':provider,'phase':phase,'n':len(group),'ok':len(accepted),
            'p50_ms':round(statistics.median(r['elapsed_ms'] for r in group),3),
            'accepted_p50_ms':round(statistics.median(r['elapsed_ms'] for r in accepted),3) if accepted else None,
            'accepted_cer_pct':round(statistics.mean(r['accepted_cer_pct'] for r in accepted),3) if accepted else None,
            'delivery_penalty_error_pct':round(statistics.mean(r['delivery_penalty_error_pct'] for r in group),3),
            'anchors_present':sum(r['anchors_present'] for r in group),'anchors_total':sum(r['anchors_total'] for r in group),
            'table_correct':sum(r['table_correct'] for r in group),'table_total':sum(r['table_total'] for r in group),
            'cache_hits':sum(r['cache_hit'] for r in group),'credits_reported':sum(r['credits_reported'] or 0 for r in group),
            'unknown_credit_records':sum(r['credits_reported'] is None for r in group),
            'native_rss_peak':max(p['native_rss_peak'] for p in profiles) if profiles else None,
            'system_nonfree_peak':max(p['system_nonfree_peak'] for p in profiles) if profiles else None,
            'compressor_peak':max(p['compressor_peak'] for p in profiles) if profiles else None,
            'available_min':min(p['available_min'] for p in profiles) if profiles else None,
            'swap_out_delta':sum(p['swap_out_delta'] for p in profiles) if profiles else None})
output={'reference_canonical_sha256':canonical,'summaries':summaries,'rows':rows,'details':details}
(ROOT/'results/analysis.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summaries,ensure_ascii=False,indent=2))
