import json,hashlib
from pathlib import Path
import pymupdf
ROOT=Path(__file__).resolve().parent
selection={'thai-gazette':[6,7,8],'thai-royal':[13,14,15],'us-census':[1,2,3],'us-preservation':[5,6,7]}
cases=[]
for ident,numbers in selection.items():
    source=ROOT/'sources'/f'{ident}.pdf';doc=pymupdf.open(source);out=pymupdf.open()
    for i,n in enumerate(numbers):
        out.insert_pdf(doc,from_page=n-1,to_page=n-1)
        page=doc[n-1]
        page.get_pixmap(matrix=pymupdf.Matrix(2,2)).save(ROOT/'review'/f'{ident}-selected-{i+1}.png')
        # Top/centre/bottom reference-review crops only; never sent to either reader.
        for name,y0,y1 in [('top',.08,.45),('bottom',.60,.96)]:
            clip=pymupdf.Rect(0,page.rect.height*y0,page.rect.width,page.rect.height*y1)
            page.get_pixmap(matrix=pymupdf.Matrix(2,2),clip=clip).save(ROOT/'review'/f'{ident}-{i+1}-{name}.png')
    path=ROOT/'public-assets'/f'{ident}.pdf';out.save(path,deflate=True)
    cases.append({'id':ident,'filename':path.name,'source_pages':numbers,'pages':3,'source_total_pages':len(doc),
        'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'text_layer_lengths':[len(p.get_text()) for p in out],'language_metadata':out.xref_get_key(out.pdf_catalog(),'Lang')})
(ROOT/'manifest.json').write_text(json.dumps({'cases':cases},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(cases))
