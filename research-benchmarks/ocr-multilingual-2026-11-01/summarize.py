import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent
items = {i['id']:i for i in json.loads((ROOT/'dataset/manifest.json').read_text(encoding='utf-8'))['items']}
summaries = []
details = []
revision_path = ROOT/'model-revisions.json'
revisions = json.loads(revision_path.read_text()) if revision_path.exists() else {}
for name in ['rapid','paddle','lighton']:
    path = ROOT/'results'/(name+'.json')
    if not path.exists():
        continue
    result = json.loads(path.read_text(encoding='utf-8'))
    if result.get('metadata',{}).get('revision'):
        revisions[result['metadata']['checkpoint']] = result['metadata']['revision']
    rows = result['rows']
    for row in rows:
        row.setdefault('cer',1.0)
    grouped = {key:[r for r in rows if r['id']==key] for key in items}
    clean = [statistics.mean(r['cer'] for r in values) for key,values in grouped.items()
             if values and items[key]['kind']=='clean-single-block' and '+' not in items[key]['languages']]
    durations = [r['elapsed_ms']/1000 for r in rows if r['ok']]
    summary = {'model':name,'fatal_error':result.get('fatal_error'),'completed':len(rows),
               'nonempty':sum(r['ok'] for r in rows),'clean_8_language_macro_cer_pct':round(statistics.mean(clean)*100,2) if clean else None,
               'all_page_macro_cer_pct':round(statistics.mean(r['cer'] for r in rows)*100,2) if rows else None,
               'warm_p50_seconds':round(statistics.median(durations),3) if durations else None,
               'warm_p95_seconds':round(sorted(durations)[max(0,__import__('math').ceil(len(durations)*.95)-1)],3) if durations else None,
               'truncated':sum(r.get('truncated',False) for r in rows),
               'load_seconds_including_downloads':round(result.get('load_ms_including_downloads',0)/1000,2),
               'first_inference_seconds':round(result.get('first_inference_ms_excluded_from_warm',0)/1000,2),
               **result.get('resources',{})}
    gpu_allocated = [r.get('gpu_allocated_peak_mib',0) for r in rows]
    summary['peak_torch_allocated_vram_mib'] = round(max(gpu_allocated),2) if gpu_allocated else None
    summary['peak_ram_including_load_mib'] = max(summary.get('peak_process_rss_mib',0),result.get('load_and_first_resources',{}).get('peak_process_rss_mib',0))
    baseline = result.get('load_and_first_resources',{}).get('idle_device_vram_mib')
    summary['device_vram_before_model_mib'] = baseline
    summary['peak_device_vram_above_pre_model_mib'] = round(max(0,summary.get('peak_device_vram_mib',0)-baseline),2) if baseline is not None else None
    summaries.append(summary)
    for key, values in grouped.items():
        if values:
            details.append({'model':name,'id':key,'languages':items[key]['languages'],
                            'cer_pct':round(statistics.mean(r['cer'] for r in values)*100,2),
                            'p50_seconds':round(statistics.median(r['elapsed_ms'] for r in values)/1000,3),
                            'completed':len(values),'nonempty':sum(r['ok'] for r in values)})
(ROOT/'results/summary.json').write_text(json.dumps({'models':summaries,'documents':details},ensure_ascii=False,indent=2),encoding='utf-8')
if revisions:
    (ROOT/'model-revisions.json').write_text(json.dumps(revisions,indent=2),encoding='utf-8')
lines = ['# Local multilingual OCR results','', '| Model | Clean 8-language CER % ↓ | All-page CER % ↓ | Warm p50 s | Warm p95 s | Peak process RAM MiB | Peak device VRAM MiB |', '|---|---:|---:|---:|---:|---:|---:|']
for r in summaries:
    lines.append(f"| {r['model']} | {r['clean_8_language_macro_cer_pct']} | {r['all_page_macro_cer_pct']} | {r['warm_p50_seconds']} | {r['warm_p95_seconds']} | {r.get('peak_process_rss_mib')} | {r.get('peak_device_vram_mib')} |")
lines += ['', 'CER is character edit rate after NFC/whitespace/Markdown normalization; lower is better. Fatal errors are not a measured quality score.', '', '| Document | Language | Rapid CER % | Paddle CER % | LightOn CER % |', '|---|---|---:|---:|---:|']
for key,item in items.items():
    scores = []
    for name in ['rapid','paddle','lighton']:
        matching = [r['cer_pct'] for r in details if r['model']==name and r['id']==key]
        scores.append(str(matching[0]) if matching else 'not measured')
    lines.append(f"| {key} | {item['languages']} | {' | '.join(scores)} |")
(ROOT/'results/summary.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps(summaries,ensure_ascii=False,indent=2))
