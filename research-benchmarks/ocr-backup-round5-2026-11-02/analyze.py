"""Score all repetitions offline; never choose a per-cell oracle ensemble."""
import hashlib,json,statistics,unicodedata
from pathlib import Path
P=Path(__file__).parent
inputs=json.loads((P/'inputs.json').read_text())
refs=json.loads((P/'references.json').read_text(encoding='utf8'))
assert inputs['reference_hash']==refs['reference_hash']=='72a37213b39a3a3dd1b4e344162d962b39c3c460fcad2bf2dfea105620301ac2'
expected={r['id']:r['expected'] for r in refs['values']}
def normalize(text):
    text=unicodedata.normalize('NFC',text)
    text=''.join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in text)
    return ''.join(c for c in text if c.isalnum() or unicodedata.category(c).startswith('M'))
summaries=[];details=[]
for mode,base in [('vl',P),('paddle_mobile',P),('tesseract_fast',P),('tesseract_best',P),('paddle_mobile_ocr',P/'supplement'),('tesseract_best_psm8',P/'wordmodes'),('tesseract_best_psm13',P/'wordmodes')]:
    data=json.loads((base/'results'/(mode+'.json')).read_text(encoding='utf8'))
    rows=data['rows'];assert len(rows)==36
    for row in rows:
        ref=next(r for r in inputs['inputs'] if r['id']==row['id'])
        assert row['input_sha256']==ref['sha256']==hashlib.sha256((P/'inputs'/ref['file']).read_bytes()).hexdigest()
        row['correct']=bool(row['complete'] and normalize(row['text'])==normalize(expected[row['id']]))
    warm=[r for r in rows if r['repeat']>0]
    samples=[json.loads(line) for line in (base/(mode+'-memory.jsonl')).read_text().splitlines()]
    summary={'mode':mode,'groups':{},'startup_seconds':data['setup']['startup_seconds'],
             'median_warm_ms':statistics.median(r['seconds'] for r in warm)*1000,
             'median_nine_image_ms':statistics.median(sum(r['seconds'] for r in warm if r['repeat']==n) for n in [1,2,3])*1000,
             'first_pass_ms':sum(r['seconds'] for r in rows if r['repeat']==0)*1000,
             'rss_sample_peak_bytes':max(s['rss'] for s in samples),
             'self_peak_rss_bytes':data['self_peak_rss_bytes'],
             'tesseract_subprocess_peak_bytes':max((r.get('child_peak_rss_bytes') or 0 for r in rows),default=0),
             'host_available_min':min(s['available'] for s in samples),
             'swap_used_min':min(s['swap_used'] for s in samples),'swap_used_max':max(s['swap_used'] for s in samples),
             'all_outputs_complete':all(r['complete'] for r in rows),
             'rss_samples':len(samples),'max_memory_sample_gap_s':max(b['time']-a['time'] for a,b in zip(samples,samples[1:])),
             'raw_result_sha256':hashlib.sha256((base/'results'/(mode+'.json')).read_bytes()).hexdigest()}
    for group in ['gazette','census']:
        cases=[c for c in inputs['inputs'] if c['group']==group]
        per_pass=[sum(r['correct'] for r in warm if r['group']==group and r['repeat']==n) for n in [1,2,3]]
        stable=0;different=0
        for case in cases:
            predictions=[r for r in warm if r['id']==case['id']]
            if all(r['correct'] for r in predictions):stable+=1
            if len(set(r['text'] for r in predictions))>1:different+=1
            details.append({'mode':mode,'id':case['id'],'group':group,'expected':expected[case['id']],
                            'predictions':[{'repeat':r['repeat'],'text':r['text'],'correct':r['correct'],'seconds':r['seconds'],'complete':r['complete']} for r in predictions]})
        summary['groups'][group]={'unique_cases':len(cases),'correct_per_warm_pass':per_pass,
                                 'stable_correct':stable,'varying_outputs':different,
                                 'median_warm_ms':statistics.median(r['seconds'] for r in warm if r['group']==group)*1000}
    summaries.append(summary)
out={'reference_hash':refs['reference_hash'],'summaries':summaries,'details':details,
     'note':'Primary four readers plus separately frozen detector-assisted supplement. Median times include each reader API/CLI overhead, not setup or harness JSON writes. RSS excludes unreported Metal allocations.'}
(P/'analysis.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(summaries,indent=2))
