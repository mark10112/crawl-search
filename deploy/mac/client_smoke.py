"""Run on the Windows client with RESEARCH_SSH_* environment variables."""
import asyncio,json,os,sys,time
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
ROOT=Path(__file__).resolve().parents[2]
DATA=Path(os.environ.get('CLIENT_SMOKE_DATA_ROOT',str(ROOT)))

async def main():
    parameters=StdioServerParameters(command=sys.executable,args=[str(ROOT/'research-tools/local-research/client.py')],env={**os.environ,'PYTHONIOENCODING':'utf-8'})
    report={'calls':[]}
    async with stdio_client(parameters) as (read,write):
        async with ClientSession(read,write) as client:
            await client.initialize();report['tools']=[t.name for t in (await client.list_tools()).tools]
            cases=[('research_health',{}),('research_search',{'query':'SearXNG','limit':3,'cache':False}),
                ('research_read',{'url':'https://docs.searxng.org/dev/search_api.html','cache':False}),
                ('research_read',{'url':'https://quotes.toscrape.com/js/','mode':'browser','cache':False}),
                ('research_read_file',{'path':str(DATA/'research-benchmarks/ocr-multilingual-2026-11-01/dataset/thai.png'),'ocr_policy':'quality','cache':False})]
            for name,args in cases:
                start=time.monotonic();r=await client.call_tool(name,args,read_timeout_seconds=__import__('datetime').timedelta(seconds=900))
                result=r.structuredContent
                if not result:result=json.loads(r.content[0].text)
                report['calls'].append({'tool':name,'seconds':round(time.monotonic()-start,3),'is_error':r.isError,'result':result})
                print(json.dumps({'tool':name,'seconds':report['calls'][-1]['seconds'],'ok':result.get('ok'),'reader':result.get('reader'),'error':result.get('error'),'results':len(result.get('results',[]))},ensure_ascii=False),flush=True)
    target=Path(os.getenv('CLIENT_SMOKE_OUTPUT',str(ROOT/'.cache/client-smoke.json')));target.parent.mkdir(exist_ok=True,parents=True);target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    assert not any(c['is_error'] for c in report['calls']),report
    assert report['calls'][0]['result']['worker_alive']
    assert all(c['result'].get('ok') for c in report['calls'][1:]),report
asyncio.run(main())
