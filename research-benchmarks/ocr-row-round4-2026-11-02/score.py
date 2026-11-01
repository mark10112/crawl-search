"""Offline scoring only; references never enter inference processes."""
import hashlib,json,re,statistics,sys,unicodedata
from pathlib import Path
from bs4 import BeautifulSoup
HERE=Path(__file__).parent
sys.path.insert(0,str(HERE.parent/'mac-vs-firecrawl-2026-11-01/.deps'))
import edlib
refs=json.loads((HERE.parent/'real-history-2026-11-01/references.json').read_text(encoding='utf8'))
digest=hashlib.sha256(json.dumps(refs,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
assert digest=='72a37213b39a3a3dd1b4e344162d962b39c3c460fcad2bf2dfea105620301ac2'
def normalize(text):
    text=BeautifulSoup(text,'html.parser').get_text(' ')
    text=unicodedata.normalize('NFC',text).translate(str.maketrans({'“':'"','”':'"','‘':"'",'’':"'",'—':'-','–':'-'}))
    text=re.sub(r'[.·_\-]{3,}','',text)
    return re.sub(r'[\s#*`|\\]','',text)
def norm(text):
    text=normalize(text).lower()
    text=''.join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in text)
    return ''.join(c for c in text if c.isalnum() or unicodedata.category(c).startswith('M'))
def content(record):return record.get('raw',{}).get('choices',[{}])[0].get('message',{}).get('content','')
def table_rows(text):
    if '<tr' in text:return [[c.get_text(' ',strip=True) for c in tr.find_all(['td','th'],recursive=False)] for tr in BeautifulSoup(text,'html.parser').find_all('tr')]
    return [[re.sub(r'<[^>]+>','',c).strip() for c in re.split(r'<(?:fcel|ecel|lcel|ucel|xcel)>',row)[1:]] for row in text.split('<nl>') if row.strip()]
cases=[]
for variant,path in [('before',HERE.parent/'ocr-accuracy-round3c-2026-11-02/results'),('after',HERE/'results')]:
    for ident in ['thai-gazette','thai-royal','us-census','us-preservation']:
        file=path/f'after-ocr-{ident}.json'
        if not file.exists():continue
        rec=json.loads(file.read_text(encoding='utf8'));raw=rec['raw'];text=raw.get('text','');ok=bool(raw.get('ok'))
        table=[{**r,'correct':bool(ok and norm(r['label']+''.join(r['values'])) in norm(text))} for r in refs['table_rows'] if r['document']==ident]
        anchors=[]
        for r in refs['anchors']:
            if r['document']!=ident:continue
            expected=normalize(r['text']);clean=normalize(text)
            cer=round(edlib.align(expected,clean,mode='HW')['editDistance']/len(expected)*100,3) if ok and clean else None
            anchors.append({'id':r['id'],'cer':cer})
        cases.append({'variant':variant,'id':ident,'ok':ok,'complete':ok and not raw.get('truncated',False),
                      'seconds':rec['elapsed_ms']/1000,'cer':round(statistics.mean(a['cer'] for a in anchors),3) if ok else None,
                      'worker_sha':rec['worker_sha'],
                      'strict_rows':sum(r['correct'] for r in table),'row_count':len(table),'table_rows':table,
                      'raw_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'source_sha256':raw.get('content_sha256')})
study=json.loads((HERE/'crop-study/results.json').read_text(encoding='utf8'))
study_rows=study['rows']; mapping={'r1':'Adams','r2':'Alexander','r3':'Cook','r4':'Woodford'}
audit=json.loads((HERE.parent/'table-error-audit-2026-11-02/audit.json').read_text(encoding='utf8'))
cells=[]
for case,label in mapping.items():
    ref=next(r for r in refs['table_rows'] if r['document']=='us-census' and r['label']==label)
    row_record=next(r for r in study_rows if r.get('case')==case and r['scope']=='row')
    whole_record=next(r for r in study_rows if r['scope']=='whole' and r['page']==ref['page'])
    def find(record):
        rows=table_rows(content(record))
        matching=[r for r in rows if r and norm(r[0])==norm(label)]
        return matching[0][1:6] if matching else []
    whole_values=find(whole_record);row_values=find(row_record)
    old=next(r for r in audit['rows'] if r['document']=='us-census' and r['label']==label)['observed_values']
    for col,expected in enumerate(ref['values']):
        cell=next(r for r in study_rows if r.get('case')==case and r['scope']=='cell' and r['column']==col+1)
        output=content(cell).strip()
        cells.append({'case':case,'label':label,'year':1900-col*10,'expected':expected,'previous_pipeline':old[col],
                      'previous_wrong':norm(old[col])!=norm(expected),
                      'whole':whole_values[col] if len(whole_values)>col else '',
                      'row':row_values[col] if len(row_values)>col else '', 'cell':output,
                      'cell_finish':cell['raw'].get('choices',[{}])[0].get('finish_reason'),
                      'cell_input_sha256':cell['input_sha256']})
        for scope,record in [('whole',whole_record),('row',row_record),('cell',cell)]:
            cells[-1][scope+'_correct']=norm(cells[-1][scope])==norm(expected) and record['raw'].get('choices',[{}])[0].get('finish_reason') in {'stop','eos_token'} and not record['raw'].get('repetition_guard',False)
summary={scope:{'correct':sum(c[scope+'_correct'] for c in cells),'total':len(cells),
                'previous_wrong_correct':sum(c[scope+'_correct'] for c in cells if c['previous_wrong']),
                'previous_wrong_total':sum(c['previous_wrong'] for c in cells),
                'control_correct':sum(c[scope+'_correct'] for c in cells if not c['previous_wrong']),
                'control_total':sum(not c['previous_wrong'] for c in cells),
                'seconds':sum(r['seconds'] for r in study_rows if r['scope']==scope)} for scope in ['whole','row','cell']}
assert len(cells)==20 and sum(c['previous_wrong'] for c in cells)==9
out={'reference_hash':digest,'documents':cases,'crop_summary':summary,'cells':cells}
(HERE/'analysis.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'documents':[{k:v for k,v in r.items() if k not in {'table_rows'}} for r in cases],'crop_summary':summary},ensure_ascii=False,indent=2))
