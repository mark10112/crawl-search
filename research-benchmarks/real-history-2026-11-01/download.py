import concurrent.futures,hashlib,json
from pathlib import Path
import httpx,pymupdf
ROOT=Path(__file__).resolve().parent
sources=[
('thai-gazette','https://www.finearts.go.th/storage/contents/2026/01/file/pW1tIxOtOfOBe9adBYoO1x4i2JZsyQkNHoqhxJb2.pdf'),
('thai-royal','https://finearts.go.th/storage/contents/file/aEPSVNEror9Xrm172S73ikol2N7ZQKovZIZ5xGYE.pdf'),
('us-preservation','https://nvlpubs.nist.gov/nistpubs/Legacy/MP/nbsmiscellaneouspub145.pdf')]
def get(pair):
    ident,url=pair
    try:
        with httpx.Client(follow_redirects=True,timeout=70,headers={'User-Agent':'HistoricalOCRBenchmark/1.0 (research; public-domain document evaluation)'}) as client:
            response=client.get(url);response.raise_for_status();data=response.content
        doc=pymupdf.open(stream=data,filetype='pdf')
        (ROOT/'sources'/f'{ident}.pdf').write_bytes(data)
        info={'id':ident,'url':url,'final_url':str(response.url),'pages':len(doc),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'text_lengths':[len(p.get_text()) for p in doc]}
        print(json.dumps({k:v for k,v in info.items() if k!='text_lengths'}),flush=True)
        for i in range(min(6,len(doc))):
            doc[i].get_pixmap(matrix=pymupdf.Matrix(1.5,1.5)).save(ROOT/'review'/f'{ident}-{i+1}.png')
        return info
    except Exception as e:
        info={'id':ident,'url':url,'error':str(e)};print(json.dumps(info),flush=True);return info
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(get,sources))
(ROOT/'sources/provenance.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
