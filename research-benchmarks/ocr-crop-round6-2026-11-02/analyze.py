"""Offline scores: clear Thai pixels primary, ambiguous Census targets separate."""
import hashlib,json,statistics,unicodedata
from pathlib import Path
P=Path(__file__).parent
inputs=json.loads((P/'inputs.json').read_text());refs=json.loads((P/'references.json').read_text(encoding='utf8'))
audit=json.loads((P/'reference-audit.json').read_text(encoding='utf8'))
expected={r['id']:r['expected'] for r in refs['values']}
def normalize(text):
    text=unicodedata.normalize('NFC',text)
    text=''.join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in text)
    return ''.join(c for c in text if c.isalnum() or unicodedata.category(c).startswith('M'))
summaries=[];details=[];models=[]
for mode in ['vl','tesseract_best']:
    data=json.loads((P/'results'/(mode+'.json')).read_text(encoding='utf8'));rows=data['rows']
    assert len(rows)==144
    for row in rows:
        case=next(c for c in inputs['inputs'] if c['id']==row['id'])
        assert row['input_sha256']==case['sha256']
        row['correct']=bool(row['complete'] and normalize(row['text'])==normalize(expected[row['source_id']]))
    samples=[json.loads(line) for line in (P/(mode+'-memory.jsonl')).read_text().splitlines()]
    models.append({'mode':mode,'startup':data['setup'],'rss_phase_peak_bytes':max(s['rss'] for s in samples),
                   'self_peak_rss_bytes':data['self_peak_rss_bytes'],'max_memory_sample_gap_s':max(b['time']-a['time'] for a,b in zip(samples,samples[1:])),
                   'tesseract_child_peak_bytes':max((r.get('child_peak_rss_bytes') or 0 for r in rows),default=0),
                   'host_available_min':min(s['available'] for s in samples),'swap_used_range':[min(s['swap_used'] for s in samples),max(s['swap_used'] for s in samples)]})
    for variant in ['original','original_pad10','tight','tight_pad10']:
        selected=[r for r in rows if r['variant']==variant and r['repeat']>0]
        inside=[s for s in samples if any(r['started_at']<=s['time']<=r['ended_at'] for r in selected)]
        summary={'mode':mode,'variant':variant,'groups':{},'incomplete_warm_calls':sum(not r['complete'] for r in selected),
                 'median_warm_ms':statistics.median(r['seconds'] for r in selected)*1000,
                 'median_nine_image_ms':statistics.median(sum(r['seconds'] for r in selected if r['repeat']==n) for n in [1,2,3])*1000,
                 'rss_in_call_windows_peak_bytes':max((s['rss'] for s in inside),default=None),'call_window_samples':len(inside),
                 'first_pass_ms':sum(r['seconds'] for r in rows if r['variant']==variant and r['repeat']==0)*1000}
        for group in ['gazette','census']:
            unique=[c['source_id'] for c in inputs['inputs'] if c['variant']==variant and c['group']==group]
            counts=[sum(r['correct'] for r in selected if r['repeat']==n and r['group']==group) for n in [1,2,3]]
            stable=0;varying=0
            for ident in unique:
                outputs=[r for r in selected if r['source_id']==ident]
                if all(r['correct'] for r in outputs):stable+=1
                if len(set(r['text'] for r in outputs))>1:varying+=1
                details.append({'mode':mode,'variant':variant,'id':ident,'group':group,'expected':expected[ident],
                                'reference_status':next(r['status'] for r in audit['rows'] if r['id']==ident),
                                'predictions':[{'repeat':r['repeat'],'text':r['text'],'correct':r['correct'],'complete':r['complete'],'seconds':r['seconds']} for r in outputs]})
            summary['groups'][group]={'n':len(unique),'correct_per_warm_pass':counts,'stable_correct':stable,'varying_outputs':varying}
        summaries.append(summary)
out={'reference_hash':inputs['reference_hash'],'reference_audit_sha256':hashlib.sha256((P/'reference-audit.json').read_bytes()).hexdigest(),
     'models':models,'summaries':summaries,'details':details,
     'policy':'Do not combine six image-confirmed Thai cases with three ambiguous-scan Census cases into a primary pixel accuracy. No per-image oracle configuration selection.'}
(P/'analysis.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'models':[{k:v for k,v in m.items() if k!='startup'} for m in models],'summaries':summaries},indent=2))
