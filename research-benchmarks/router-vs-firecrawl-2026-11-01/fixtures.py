import hashlib
import html
import json
from pathlib import Path
import pymupdf

ROOT=Path(__file__).resolve().parent
source=ROOT.parent/'ocr-multilingual-2026-11-01/dataset'
out=ROOT/'public-assets'
out.mkdir(exist_ok=True)
items=json.loads((source/'manifest.json').read_text(encoding='utf-8'))['items']
cases=[]
for item in items:
    path=out/(item['id']+'.pdf')
    doc=pymupdf.open()
    page=doc.new_page(width=600,height=750)
    page.insert_image(page.rect,filename=str(source/item['image']))
    # Real source metadata, supplied identically to both readers; no reference text embedded.
    doc.xref_set_key(doc.pdf_catalog(),'Lang','('+ (item['languages'] if '+' not in item['languages'] else 'mul') +')')
    doc.set_metadata({'title':'Controlled multilingual OCR document'})
    doc.save(path,deflate=True)
    doc.close()
    cases.append({'id':item['id'],'filename':path.name,'kind':'scanned-pdf','language_metadata':item['languages'],
                  'reference':item['reference'],'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
for name,base,dynamic in [('static-english','english',False),('static-french','french',False),('dynamic-english','english',True)]:
    reference=next(i['reference'] for i in items if i['id']==base)
    if dynamic:
        content='<main id="content"></main><script>setTimeout(()=>{document.getElementById("content").innerText='+json.dumps(reference)+'},250)</script>'
    else:
        content='<main><article>'+html.escape(reference).replace('\n','<br>')+'</article></main>'
    path=out/(name+'.html')
    path.write_text('<!doctype html><html><head><meta charset="utf-8"><title>Research source</title></head><body>'+content+'</body></html>',encoding='utf-8')
    cases.append({'id':name,'filename':path.name,'kind':'javascript' if dynamic else 'html','reference':reference,
                  'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
reference=items[0]['reference']
doc=pymupdf.open()
page=doc.new_page()
page.insert_textbox(pymupdf.Rect(50,60,550,700),reference,fontsize=13)
path=out/'digital-english.pdf'
doc.save(path)
doc.close()
cases.append({'id':'digital-english','filename':path.name,'kind':'digital-pdf','reference':reference,
              'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
(ROOT/'manifest.json').write_text(json.dumps({'cases':cases},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'cases':len(cases),'only_public_files':str(out)}))
