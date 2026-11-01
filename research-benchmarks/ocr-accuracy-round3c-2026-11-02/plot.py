import json,sys
from pathlib import Path
R=Path(__file__).resolve().parent
sys.path.insert(0,str(R.parent/'mac-vs-firecrawl-2026-11-01/.deps'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
rows=json.loads((R/'results/analysis.json').read_text())['rows']
raw=[json.loads(p.read_text(encoding='utf-8')) for p in (R/'results').glob('*.json') if p.name.startswith(('before-auto-','before-ocr-','after-auto-','after-ocr-'))]
samples=[json.loads(l) for l in (R/'results/memory.jsonl').read_text().splitlines()]
start=min(r['started_at'] for r in raw);end=max(r['ended_at'] for r in raw)
samples=[s for s in samples if start-3<=s['time']<=end+1]
fig=plt.figure(figsize=(12,9),layout='constrained')
grid=fig.add_gridspec(2,2,height_ratios=[1.3,1])
ax=fig.add_subplot(grid[0,:])
mem_before=fig.add_subplot(grid[1,0]);mem_after=fig.add_subplot(grid[1,1],sharey=mem_before)
ids=['thai-gazette','thai-royal','us-census','us-preservation']
for i,ident in enumerate(ids):
    for variant,offset,color in [('before',-.18,'#98A3B5'),('after',.18,'#176B87')]:
        r=next(r for r in rows if (r['variant'],r['mode'],r['id'])==(variant,'ocr',ident))
        ax.barh(i+offset,r['seconds'],height=.32,color=color,hatch=None if r['ok'] else '///',edgecolor='white')
        suffix=(f"CER {r['accepted_cer_pct']:.1f}%"+(' (40k cap)' if r.get('output_truncated') else '')) if r['ok'] else 'rejected'
        ax.text(r['seconds']+.6,i+offset,f"{r['seconds']:.1f}s / {suffix}",va='center',fontsize=8)
ax.set_yticks(range(4),ids);ax.invert_yaxis();ax.set_xlim(0,max(r['seconds'] for r in rows)*1.45)
ax.set_xlabel('Seconds to full result or rejection (forced OCR, cache off)')
ax.set_title('Same historical PDFs: forced OCR before / after',loc='left',weight='bold')
ax.legend(handles=[Patch(color='#98A3B5',label='Before: 144 DPI + guard'),Patch(color='#176B87',label='After: format-aware guard + adaptive detail'),Patch(facecolor='white',edgecolor='#758095',hatch='///',label='Completion gate rejected')],loc='lower right',frameon=False,fontsize=8)
ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
# Do not interpolate across the diagnostic/experiment gap in reused-baseline runs.
max_duration=max((max(r['ended_at'] for r in raw if r['variant']==v)-min(r['started_at'] for r in raw if r['variant']==v))/60 for v in ['before','after'])
for variant,mem in [('before',mem_before),('after',mem_after)]:
    begin=min(r['started_at'] for r in raw if r['variant']==variant)
    finish=max(r['ended_at'] for r in raw if r['variant']==variant)
    phase=[s for s in samples if begin-2<=s['time']<=finish+1]
    t=[(s['time']-begin)/60 for s in phase]
    for key,label,color in [('native_rss','API / OCR / MLX RSS','#176B87'),('available_bytes','Host available','#3D8355'),('compressor_bytes','Host compressed','#DB7C26')]:
        mem.plot(t,[s[key]/1024**3 for s in phase],label=label,color=color,lw=1.1)
    mem.set_title(variant.capitalize()+' memory (measured interval only)',loc='left',weight='bold')
    mem.set_xlim(0,max_duration+.1);mem.set_ylim(bottom=0)
    mem.set_xlabel('Minutes since first '+variant+' read');mem.set_ylabel('GiB');mem.grid(alpha=.15)
    mem.legend(frameon=False,fontsize=8,loc='best')
fig.suptitle('Table source fidelity: Mac M4 reused-baseline follow-up',weight='bold',fontsize=13)
fig.savefig(R/'comparison.png',dpi=160)
print(R/'comparison.png')
