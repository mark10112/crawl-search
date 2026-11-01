"""Score unchanged source-image references; separate rejection from accepted-output CER."""
import hashlib,json,re,statistics,sys,unicodedata
from functools import lru_cache
from pathlib import Path
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'mac-vs-firecrawl-2026-11-01/.deps'))
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

samples=[json.loads(l) for l in (ROOT/'results/memory.jsonl').read_text().splitlines()]
telemetry=[json.loads(l) for l in (ROOT/'results/telemetry.jsonl').read_text().splitlines()]
rows=[];details=[]
for path in sorted((ROOT/'results').glob('*.json')):
    if not path.name.startswith(('before-auto-','before-ocr-','after-auto-','after-ocr-')):continue
    rec=json.loads(path.read_text(encoding='utf-8'));raw=rec['raw'];ok=bool(raw.get('ok'));text=raw.get('text','');clean=normalize(text)
    anchors=[]
    for ref in refs['anchors']:
        if ref['document']!=rec['id']:continue
        cer,prediction=align(normalize(ref['text']),clean)
        anchors.append({'id':ref['id'],'page':ref['page'],'accepted_cer_pct':round(100*cer,3) if ok else None,
            'delivery_penalty_pct':round(100*cer,3) if ok else 100,'present':ok and cer<=.2,'expected':ref['text'],'prediction':prediction})
    tables=[];flat=table_norm(text)
    for ref in refs['table_rows']:
        if ref['document']==rec['id']:tables.append({**ref,'correct':bool(ok and table_norm(ref['label']+''.join(ref['values'])) in flat)})
    calls=[r for r in telemetry if r.get('variant')==rec['variant'] and r.get('mode')==rec['mode'] and r.get('id')==rec['id'] and r['kind']=='generation']
    inside=[s for s in samples if rec['started_at']<=s['time']<=rec['ended_at']]
    bracketed=False
    if not inside:
        a=[s for s in samples if s['time']<rec['started_at']];b=[s for s in samples if s['time']>rec['ended_at']]
        inside=([a[-1]] if a else [])+([b[0]] if b else []);bracketed=True
    case=next(c for c in manifest['cases'] if c['id']==rec['id'])
    assert raw['content_sha256']==case['sha256']
    row={'variant':rec['variant'],'mode':rec['mode'],'id':rec['id'],'ok':ok,'seconds':round(rec['elapsed_ms']/1000,3),
        'complete_output':bool(ok and not raw.get('truncated',False)),'reader':raw.get('reader'),'chars':len(text),'output_truncated':raw.get('truncated',False),'error':raw.get('error'),'accepted_cer_pct':round(statistics.mean(a['accepted_cer_pct'] for a in anchors),3) if ok else None,
        'delivery_penalty_pct':round(statistics.mean(a['delivery_penalty_pct'] for a in anchors),3),'anchors_present':sum(a['present'] for a in anchors),
        'table_correct':sum(t['correct'] for t in tables),'table_total':len(tables),'generation_count':len(calls),
        'sent_limits':sorted(set(c.get('max_tokens') for c in calls)),
        'sent_penalties':sorted(set(c.get('repetition_penalty') for c in calls),key=lambda x: str(x)),'length_stops':sum(c.get('finish_reason')=='length' for r in calls for c in r.get('choices',[])),
        'normal_stops':sum(c.get('finish_reason')=='stop' for r in calls for c in r.get('choices',[])),
        'max_generated_tokens':max((r.get('usage') or {}).get('completion_tokens',0) for r in calls) if calls else 0,
        'native_rss_peak':max(s['native_rss'] for s in inside),'available_min':min(s['available_bytes'] for s in inside),
        'compressor_peak':max(s['compressor_bytes'] for s in inside),'system_nonfree_peak':max(s['system_nonfree_bytes'] for s in inside),
        'memory_bracketed':bracketed,'swap_out_delta':inside[-1]['swap_out_bytes']-inside[0]['swap_out_bytes']}
    pages=[r['result'] for r in telemetry if r.get('variant')==rec['variant'] and r.get('mode')==rec['mode'] and r.get('id')==rec['id'] and r['kind']=='page']
    row['diagnostic_pages_observed']=len(pages)
    row['normal_pages']=sum(bool(p.get('ok')) for p in pages)
    row['region_counts']=[len(p.get('regions',[])) for p in pages]
    row['original_markup_chars']=sum(p.get('original_markup_chars',len(p.get('text',''))) for p in pages)
    if len(pages)==3 and all(p.get('ok') for p in pages):
        full='\n\n'.join(p['text'] for p in pages);full_clean=normalize(full);full_flat=table_norm(full)
        spans=[r for r in refs['anchors'] if r['document']==rec['id']]
        row['diagnostic_pre_char_cap_cer_pct']=round(statistics.mean(align(normalize(r['text']),full_clean)[0]*100 for r in spans),3)
        row['diagnostic_pre_char_cap_table_correct']=sum(table_norm(r['label']+''.join(r['values'])) in full_flat for r in refs['table_rows'] if r['document']==rec['id'])
        row['diagnostic_pre_char_cap_chars']=len(full)
    rows.append(row);details.append({'file':path.name,'anchors':anchors,'tables':tables})
summary=[]
for variant in ['before','after']:
    for mode in ['auto','ocr']:
        group=[r for r in rows if r['variant']==variant and r['mode']==mode]
        if not group:continue
        accepted=[r for r in group if r['ok']]
        summary.append({'variant':variant,'mode':mode,'n':len(group),'ok':len(accepted),'complete_output':sum(r['complete_output'] for r in group),'median_seconds':statistics.median(r['seconds'] for r in group),
            'accepted_cer_pct':round(statistics.mean(r['accepted_cer_pct'] for r in accepted),3) if accepted else None,
            'delivery_penalty_pct':round(statistics.mean(r['delivery_penalty_pct'] for r in group),3),
            'table_correct':sum(r['table_correct'] for r in group),'table_total':sum(r['table_total'] for r in group),
            'length_stops':sum(r['length_stops'] for r in group),'native_rss_peak':max(r['native_rss_peak'] for r in group),
            'available_min':min(r['available_min'] for r in group),'compressor_peak':max(r['compressor_peak'] for r in group)})
output={'summaries':summary,'rows':rows,'details':details,'reference_hash':canonical}
(ROOT/'results/analysis.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))

