import json,sys
from pathlib import Path
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R/'.deps'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

rows=json.loads((R/'results/analysis.json').read_text())['rows']
raw=[json.loads(p.read_text(encoding='utf-8')) for p in (R/'results').glob('mac-*.json')]
raw=[r for r in raw if 'started_at' in r]
samples=[json.loads(l) for l in (R/'results/memory.jsonl').read_text().splitlines()]
start=min(r['started_at'] for r in raw);end=max(r['ended_at'] for r in raw)
samples=[s for s in samples if start-5<=s['time']<=end+1]
fig,(ax,mem)=plt.subplots(2,1,figsize=(12,9),gridspec_kw={'height_ratios':[1,1.2]},layout='constrained')
ids=['thai-gazette','thai-royal','us-census','us-preservation']
labels=['Thai contents / scanned','Thai chronicle / scanned','US Census / existing text layer','US preservation / existing text layer']
for i,ident in enumerate(ids):
    for provider,offset,color in [('mac',-.18,'#176B87'),('firecrawl',.18,'#DB7C26')]:
        r=next(r for r in rows if (r['provider'],r['phase'],r['id'])==(provider,'off',ident))
        value=r['elapsed_ms']/1000
        ax.barh(i+offset,value,.32,color=color if r['ok'] else '#ADB6C1',hatch=None if r['ok'] else '///',edgecolor='white')
        ax.text(value+.5,i+offset,f'{value:.2f}s'+(' (rejected)' if not r['ok'] else ''),va='center',fontsize=9)
ax.set_yticks(range(4),labels);ax.invert_yaxis();ax.set_xlim(0,71);ax.set_xlabel('Seconds to final response, including rejection')
ax.set_title('Cache off: same four three-page historical PDFs',loc='left',weight='bold')
ax.legend(handles=[Patch(color='#176B87',label='Mac accepted'),Patch(color='#DB7C26',label='Firecrawl'),Patch(facecolor='#ADB6C1',hatch='///',label='Mac rejected incomplete generation')],loc='lower right',frameon=False)
ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
t=[(s['time']-start)/60 for s in samples]
for key,label,color in [('system_nonfree_bytes','Host nonfree (includes reclaimable cache)','#939BA8'),('native_rss','Native OCR / MLX / APIs RSS','#176B87'),('compressor_bytes','Host compressor (already in host total)','#DB7C26'),('available_bytes','Host available (psutil estimate)','#3D8355')]:
    mem.plot(t,[s[key]/1024**3 for s in samples],label=label,color=color,lw=1.3)
for provider,phase,label in [('mac','off','off'),('mac','prime','prime'),('mac','hit','repeat'),('mac-forced-quality','off','forced OCR')]:
    part=[r for r in raw if r['provider']==provider and r['phase']==phase]
    a=(min(r['started_at'] for r in part)-start)/60;b=(max(r['ended_at'] for r in part)-start)/60
    mem.axvline(a,color='#CFD5DE',lw=.7);mem.text((a+b)/2,16.25,label,ha='center',va='bottom',fontsize=9)
mem.set_ylim(0,17);mem.set_xlim(min(t),max(t));mem.set_ylabel('GiB');mem.set_xlabel('Minutes since first Mac request')
mem.set_title('Mac 16 GiB unified memory; sampled every 0.5 seconds',loc='left',weight='bold')
mem.grid(alpha=.15);mem.legend(loc='center left',bbox_to_anchor=(0,0.61),frameon=False,fontsize=8)
fig.suptitle('Mac mini M4 vs Firecrawl — measured deployment behavior',fontsize=14,weight='bold')
fig.savefig(R/'benchmark.png',dpi=160)
print(R/'benchmark.png')
