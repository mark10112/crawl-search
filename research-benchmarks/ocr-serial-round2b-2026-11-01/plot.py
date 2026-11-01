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
fig,(ax,mem)=plt.subplots(2,1,figsize=(12,8.5),layout='constrained')
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
ax.legend(handles=[Patch(color='#98A3B5',label='Before: 8192, no penalty'),Patch(color='#176B87',label='After: 8192, serialized'),Patch(facecolor='white',edgecolor='#758095',hatch='///',label='Completion gate rejected')],loc='lower right',frameon=False,fontsize=8)
ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
t=[(s['time']-start)/60 for s in samples]
for key,label,color in [('native_rss','Native API / OCR / MLX RSS','#176B87'),('available_bytes','Host available','#3D8355'),('compressor_bytes','Host compressed RAM','#DB7C26')]:
    mem.plot(t,[s[key]/1024**3 for s in samples],label=label,color=color,lw=1.2)
after=min(r['started_at'] for r in raw if r['variant']=='after')
before_end=max(r['ended_at'] for r in raw if r['variant']=='before')
mem.axvspan((before_end-start)/60,(after-start)/60,color='#E8E8E8',label='MLX reset + identical warm-up')
mem.axvline((after-start)/60,color='#B0B0B0',lw=.8)
mem.set_xlabel('Minutes since first measured before request');mem.set_ylabel('GiB');mem.set_ylim(bottom=0)
mem.set_title('Mac memory; production admission paused, one layout worker',loc='left',weight='bold')
mem.legend(frameon=False,fontsize=8,loc='best');mem.grid(alpha=.15)
fig.suptitle('Serialized recognition + complete output: Mac M4 follow-up',weight='bold',fontsize=14)
fig.savefig(R/'comparison.png',dpi=160)
print(R/'comparison.png')
