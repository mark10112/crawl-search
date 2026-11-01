"""Pre-inference evidence/ground-truth audit and fixed 2x2 crop preparation."""
import hashlib,json,shutil,sys
from pathlib import Path
import pymupdf
from PIL import Image,ImageDraw
from crop_geometry import variants

ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
WORK=Path(sys.argv[1]) if len(sys.argv)>1 else Path.home()/'research-server/benchmarks/ocr-crop-round6-2026-11-02'
WORK.mkdir(parents=True,exist_ok=True)
assert not (WORK/'inputs.json').exists(),'Do not overwrite frozen experiment'
OLD=ROOT/'research-benchmarks/ocr-backup-round5-2026-11-02'
manifest=json.loads((OLD/'inputs.json').read_text());references=json.loads((OLD/'references.json').read_text())
SOURCE=ROOT/'.cache/ocr-diagnosis'
if not SOURCE.exists():SOURCE=Path.home()/'research-server/releases/2026-11-01-ocr/research-benchmarks/real-history-2026-11-01/public-assets'
original=json.loads((ROOT/'research-benchmarks/real-history-2026-11-01/manifest.json').read_text())
pdfs={}
for ident in ['thai-gazette','us-census']:
    file=SOURCE/(ident+'.pdf');sha=hashlib.sha256(file.read_bytes()).hexdigest()
    assert sha==next(c['sha256'] for c in original['cases'] if c['id']==ident)
    pdfs[ident]=pymupdf.open(file)
OUT=WORK/'inputs';OUT.mkdir();evidence=WORK/'evidence';evidence.mkdir()
frozen=[];audits=[]
sources={
 'r1-c3':{'url':'https://www2.census.gov/library/publications/decennial/1890/bulletins/demographics/145-population-of-il.pdf','evidence':'1890 Bulletin 145, page 1 SUMMARY BY COUNTIES: Adams 1880 = 59,135'},
 'r3-c1':{'url':'https://www2.census.gov/library/publications/decennial/1910/bulletins/demographics/360-population-by-counties-minor-civil-divisions-1910-1900-1890-part-1.pdf','evidence':'1910 Bulletin 360, Illinois Table 1: Cook County 1900 = 1,838,735; also Table 4 in original Bulletin 21'},
 'r4-c5':{'url':'https://www2.census.gov/library/publications/decennial/1860/statistics/1860d-13.pdf','evidence':'1860 Statistics county table: Woodford population = 13,282; corroborated by official Woodford County Census Data Chart'}
}
for case in manifest['inputs']:
    data=(OLD/'inputs'/case['file']).read_bytes();assert hashlib.sha256(data).hexdigest()==case['sha256']
    image=Image.open(OLD/'inputs'/case['file']).convert('RGB')
    ident='thai-gazette' if case['group']=='gazette' else 'us-census'
    page=pdfs[ident][case['provenance']['page']-1];b=case['provenance']['bbox']
    # Wider source context for audit only, not an OCR input. 600-DPI rendering
    # does not create new scan information; keep this explicit in the ledger.
    context=pymupdf.Rect(max(0,b[0]-220)*72/300,max(0,b[1]-30)*72/300,min(page.rect.width,(b[2]+50)*72/300),min(page.rect.height,(b[3]+30)*72/300))
    page.get_pixmap(dpi=600,clip=context).save(evidence/(case['id']+'-context600.png'))
    expected=next(r['expected'] for r in references['values'] if r['id']==case['id'])
    audits.append({'id':case['id'],'expected_unchanged':expected,'group':case['group'],
                   'status':'image_confirmed' if case['group']=='gazette' else 'intended_value_corroborated_but_scan_glyph_ambiguous',
                   'primary_pixel_accuracy':case['group']=='gazette',
                   'source_document':ident,'source_page':case['provenance']['page'],
                   'context':case['id']+'-context600.png','crosscheck':sources.get(case['id']),
                   'note':'600 DPI is inspection enlargement, not recovered detail. Old OCR text layer is not ground truth.'})
    for variant,pixels,box,padding in variants(image):
        key=case['id']+'__'+variant;file=OUT/(key+'.png')
        if variant=='original':file.write_bytes(data)
        else:pixels.save(file)
        frozen.append({'id':key,'source_id':case['id'],'variant':variant,'file':file.name,'group':case['group'],'language':case['language'],
                       'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'parent_sha256':case['sha256'],
                       'source_local_bbox':box,'padding':padding,'size':list(pixels.size),
                       'primary_pixel_accuracy':case['group']=='gazette'})
    # Review sheet at nearest-neighbour enlargement; not passed to models.
    sheet=Image.new('RGB',(4*460,190),'#dddddd');draw=ImageDraw.Draw(sheet)
    for j,(variant,pixels,box,padding) in enumerate(variants(image)):
        draw.text((j*460+5,5),case['id']+' / '+variant,fill='black')
        factor=min(4,430/max(1,pixels.width),145/max(1,pixels.height))
        enlarged=pixels.resize((round(pixels.width*factor),round(pixels.height*factor)),Image.Resampling.NEAREST)
        sheet.paste(enlarged,(j*460+5,35))
    sheet.save(evidence/(case['id']+'-variants.png'))
ledger={'reference_hash':manifest['reference_hash'],'values_changed':False,'audit_order':'Sources inspected and this ledger frozen before inference.',
        'reviewer_count':1,'primary_image_confirmed_count':6,'ambiguous_scan_count':3,'rows':audits,
        'policy':'Six clear Thai values are primary pixel-accuracy set. Keep intended-value scores for the three Census cells separately, with same historical references. Do not relabel ambiguous glyphs to match OCR majority; do not claim OCR failures there are purely model failures.'}
(WORK/'inputs.json').write_text(json.dumps({'reference_hash':manifest['reference_hash'],'inputs':frozen},indent=2))
(WORK/'references.json').write_text(json.dumps(references,ensure_ascii=False,indent=2))
(WORK/'reference-audit.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2))
shutil.copy2(OLD/'models.json',WORK/'models.json')
print(json.dumps({'variants':len(frozen),'image_confirmed':6,'corroborated_but_ambiguous':3,'reference_values_changed':False}))
