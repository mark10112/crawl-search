import hashlib,json,re,statistics,unicodedata,sys,os
from pathlib import Path
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'.deps'))
import edlib
from functools import lru_cache
reference_file=ROOT/os.getenv('BENCH_REFERENCE','references.json')
refs=json.loads(reference_file.read_text(encoding='utf-8'))
manifest=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))
def normalize(text):
    text=BeautifulSoup(text,'html.parser').get_text(' ')
    text=unicodedata.normalize('NFC',text).translate(str.maketrans({'“':'"','”':'"','‘':"'",'’':"'",'—':'-','–':'-'}))
    text=re.sub(r'[.·_\-]{3,}','',text)
    return re.sub(r'[\s#*`|\\]','',text)
def table_norm(text):
    text=normalize(text).lower()
    text=''.join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in text)
    return ''.join(c for c in text if c.isalnum() or unicodedata.category(c).startswith('M'))
rows=[];details=[]
@lru_cache(maxsize=2000)
def align(expected,clean):
    if not clean:return 1.0,'',None,None
    result=edlib.align(expected,clean,mode='HW',task='locations')
    start,end=result['locations'][0]
    return result['editDistance']/len(expected),clean[start:end+1],start,end+1
for path in sorted((ROOT/'results').glob('*.json')):
    if not path.name.startswith(('local-off-','local-prime-','local-hit-','local-forced-quality-off-','firecrawl-off-','firecrawl-prime-','firecrawl-hit-')):continue
    rec=json.loads(path.read_text(encoding='utf-8'));raw=rec['raw'];local=rec['provider'].startswith('local')
    text=raw.get('text','') if local else raw.get('markdown','');clean=normalize(text)
    ok=raw.get('ok',False) if local else bool(text) and not raw.get('error')
    anchors=[]
    for ref in refs['anchors']:
        if ref['document']!=rec['id']:continue
        expected=normalize(ref['text']);cer,predicted,start,end=align(expected,clean)
        if not ok:cer=1
        anchors.append({'id':ref['id'],'page':ref['page'],'region':ref['region'],'cer_pct':round(cer*100,3),
            'present_20pct':ok and cer<=.2,'expected':expected,'aligned_prediction':predicted,
            'start':start,'end':end})
    tables=[];flat=table_norm(text)
    for ref in refs['table_rows']:
        if ref['document']!=rec['id']:continue
        expected=table_norm(ref['label']+''.join(ref['values']))
        tables.append({**ref,'tuple_present':ok and expected in flat})
    case=next(c for c in manifest['cases'] if c['id']==rec['id'])
    row={'provider':rec['provider'],'phase':rec['phase'],'id':rec['id'],'ok':ok,'elapsed_ms':rec['elapsed_ms'],
         'credits_used':rec.get('credits_used'),'chars':len(text),'reader':raw.get('reader'),
         'cache_hit':raw.get('cache_hit',False) if local else raw.get('metadata',{}).get('cacheState')=='hit',
         'cache_state':raw.get('cache_hit') if local else raw.get('metadata',{}).get('cacheState'),
         'sample_cer_pct':round(statistics.mean(r['cer_pct'] for r in anchors),3),
         'anchors_present':sum(r['present_20pct'] for r in anchors),'anchors_total':len(anchors),
         'table_rows_correct':sum(r['tuple_present'] for r in tables),'table_rows_total':len(tables),
         'hash_matches':raw.get('content_sha256')==case['sha256'] if local else None}
    rows.append(row);details.append({'file':path.name,'anchors':anchors,'tables':tables})
summaries=[]
for provider in ['local','firecrawl','local-forced-quality']:
    for phase in ['off','prime','hit']:
        group=[r for r in rows if r['provider']==provider and r['phase']==phase]
        if not group:continue
        summaries.append({'provider':provider,'phase':phase,'n':len(group),'ok':sum(r['ok'] for r in group),
            'p50_ms':round(statistics.median(r['elapsed_ms'] for r in group),2),'max_ms':max(r['elapsed_ms'] for r in group),
            'sample_cer_pct':round(statistics.mean(r['sample_cer_pct'] for r in group),3),
            'anchors_present':sum(r['anchors_present'] for r in group),'anchors_total':sum(r['anchors_total'] for r in group),
            'table_rows_correct':sum(r['table_rows_correct'] for r in group),'table_rows_total':sum(r['table_rows_total'] for r in group),
            'cache_hits':sum(r['cache_hit'] for r in group),'credits_used':sum(r['credits_used'] or 0 for r in group),
            'unknown_credit_records':sum(r['credits_used'] is None for r in group)})
output={'reference_hash':hashlib.sha256(reference_file.read_bytes()).hexdigest(),'summaries':summaries,'rows':rows,'details':details}
(ROOT/'results'/os.getenv('BENCH_ANALYSIS','analysis.json')).write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summaries,indent=2))
