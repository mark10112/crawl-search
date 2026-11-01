"""Client-side upload/hash/PDF/reconnect check, with an optional real table page."""
import asyncio,hashlib,json,os,sys,tempfile,time
from datetime import timedelta
from pathlib import Path
import pymupdf
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT=Path(__file__).resolve().parents[2]
PARAMS=StdioServerParameters(command=sys.executable,args=[str(ROOT/'research-tools/local-research/client.py')],env={**os.environ,'PYTHONIOENCODING':'utf-8'})

async def call(client,name,args):
    r=await client.call_tool(name,args,read_timeout_seconds=timedelta(seconds=660))
    assert not r.isError,r
    return r.structuredContent or json.loads(r.content[0].text)

async def main():
    report={}
    with tempfile.TemporaryDirectory() as temp:
        path=Path(temp)/'two-pages.pdf'
        with pymupdf.open() as doc:
            for n in [1,2]:
                page=doc.new_page()
                page.insert_text((60,60),f'PAGE {n}: The research committee reviewed the public revenue and expenditure accounts.\nThis is a two-page digital document used to verify page bounds and transfer integrity.\n'+('ALPHA' if n==1 else 'OMEGA'))
            doc.save(path)
        async with stdio_client(PARAMS) as (read,write):
            async with ClientSession(read,write) as client:
                await client.initialize()
                start=time.monotonic();pdf=await call(client,'research_read_file',{'path':str(path),'max_pages':2,'cache':False})
                assert pdf['ok'] and pdf['reader']=='pdf-text' and pdf['pages_read']==[1,2],pdf
                assert 'ALPHA' in pdf['text'] and 'OMEGA' in pdf['text']
                assert pdf['content_sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
                report['pdf']={'seconds':round(time.monotonic()-start,3),'result':pdf}
                table=os.getenv('RESEARCH_SMOKE_TABLE')
                if table:
                    start=time.monotonic();result=await call(client,'research_read_file',{'path':table,'cache':False,'ocr_policy':'quality'})
                    report['table']={'seconds':round(time.monotonic()-start,3),'result':result}
                urls=['https://docs.searxng.org/dev/search_api.html']*2
                duplicates=await call(client,'research_read_many',{'urls':urls})
                # FastMCP wraps a list in the result field of structured output.
                if isinstance(duplicates,dict):duplicates=duplicates['result']
                assert all(x['ok'] for x in duplicates)
                assert duplicates[0]['job_id']==duplicates[1]['job_id']
                report['duplicate_url_job']=duplicates[0]['job_id']
        async with stdio_client(PARAMS) as (read,write):
            async with ClientSession(read,write) as client:
                await client.initialize();job=await call(client,'research_job',{'job_id':pdf['job_id']})
                assert job['status']=='complete' and job['result']['content_sha256']==pdf['content_sha256']
                report['reconnect_preserved_job']=pdf['job_id']
    target=Path(os.environ['DOCUMENT_SMOKE_OUTPUT']);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'pdf_seconds':report['pdf']['seconds'],'hash_verified':True,'reconnect':True,'duplicates_share_job':True,'table_seconds':report.get('table',{}).get('seconds'),'table_ok':report.get('table',{}).get('result',{}).get('ok'),'table_error':report.get('table',{}).get('result',{}).get('error')},ensure_ascii=False))

if __name__=='__main__':asyncio.run(main())
