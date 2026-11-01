"""Thin Windows/client MCP bridge. SSH carries data; all readers run on the server."""
import asyncio,os,socket,subprocess,time
from pathlib import Path
from contextlib import asynccontextmanager
import httpx
from mcp.server.fastmcp import FastMCP

client=None;tunnel=None
@asynccontextmanager
async def lifespan(server):
    global client,tunnel
    base=os.getenv('RESEARCH_REMOTE_URL')
    if not base:
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        host=os.environ['RESEARCH_SSH_HOST'];key=os.environ['RESEARCH_SSH_KEY'];known=os.environ['RESEARCH_SSH_KNOWN_HOSTS']
        args=['ssh','-N','-T','-i',key,'-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o',f'UserKnownHostsFile={known}','-o','ExitOnForwardFailure=yes','-o','ServerAliveInterval=20','-o','ServerAliveCountMax=3','-L',f'127.0.0.1:{port}:127.0.0.1:8768',host]
        tunnel=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        base=f'http://127.0.0.1:{port}'
    client=httpx.AsyncClient(base_url=base,timeout=30)
    try:
        for attempt in range(40):
            try:
                response=await client.get('/health');response.raise_for_status();break
            except httpx.HTTPError:
                if tunnel and tunnel.poll() is not None:raise RuntimeError('SSH tunnel failed; verify host/key and server service')
                if attempt==39:raise
                await asyncio.sleep(.25)
        yield {}
    finally:
        await client.aclose()
        if tunnel:tunnel.terminate();await asyncio.to_thread(tunnel.wait)
mcp=FastMCP('local-research',lifespan=lifespan)
async def post(path,args):
    response=await client.post(path,json=args);response.raise_for_status();return response.json()
async def wait(job,timeout=600):
    started=time.monotonic()
    while job['status'] in {'queued','running'}:
        if time.monotonic()-started>timeout:return {'ok':False,'pending':True,'job_id':job['id'],'next_step':'Use research_job; the server continues the job.'}
        await asyncio.sleep(.5);r=await client.get('/jobs/'+job['id']);r.raise_for_status();job=r.json()
    return {**(job.get('result') or {'ok':False,'error':'Job failed'}),'job_id':job['id']}
@mcp.tool()
async def research_health()->dict:
    """Inspect the remote Mac search/reader/OCR services."""
    r=await client.get('/health');r.raise_for_status();return r.json()
@mcp.tool()
async def research_search(query:str,limit:int=5,cache:bool=True)->dict:
    """Search SearXNG on the Mac. Snippets are not full evidence; inspect engine errors."""
    return await post('/search',{'query':query,'limit':limit,'cache':cache})
@mcp.tool()
async def research_submit(url:str,max_pages:int=5,start_page:int=1,cache:bool=True,ocr_policy:str='balanced',mode:str='auto')->dict:
    """Submit a durable remote read. Returns a job ID immediately; use research_job for results."""
    return await post('/jobs',{'url':url,'max_pages':max_pages,'start_page':start_page,'cache':cache,'ocr_policy':ocr_policy,'mode':mode})
@mcp.tool()
async def research_job(job_id:str)->dict:
    """Get persistent job status/result, including after reconnecting the MCP client."""
    r=await client.get('/jobs/'+job_id);r.raise_for_status();return r.json()
@mcp.tool()
async def research_read(url:str,max_pages:int=5,start_page:int=1,max_chars:int=22000,cache:bool=True,ocr_engine:str='auto',language_hint:str|None=None,ocr_policy:str='balanced',mode:str='auto')->dict:
    """Read remotely and wait up to ten minutes. Incomplete OCR is not successful evidence. Firecrawl handoff remains a client tool."""
    return await wait(await post('/jobs',locals()))
@mcp.tool()
async def research_read_file(path:str,max_pages:int=5,ocr_policy:str='balanced',start_page:int=1,cache:bool=True,mode:str='auto')->dict:
    """Upload a local client PDF/image once by content hash and read it on Mac. Max 32 MiB."""
    source=Path(path).expanduser()
    if source.stat().st_size>32*1024*1024:raise ValueError('File exceeds 32 MiB')
    r=await client.post('/uploads',content=source.read_bytes());r.raise_for_status()
    return await wait(await post('/jobs',{'upload_id':r.json()['upload_id'],'max_pages':max_pages,'start_page':start_page,'cache':cache,'mode':mode,'ocr_policy':ocr_policy}))
@mcp.tool()
async def research_complete_fallback(request_id:str,markdown:str,metadata:dict,credits_used:int|None=None)->dict:
    """Cache a real connected Firecrawl result on Mac after the requested client-agent handoff."""
    return await post('/complete',{'request_id':request_id,'text':markdown,'metadata':metadata,'credits_used':credits_used})
@mcp.tool()
async def research_read_many(urls:list[str],max_pages:int=5,max_chars:int=12000)->list[dict]:
    """Submit up to ten URLs; Mac serialises heavy work. Identical URLs share one job."""
    jobs={}
    for url in urls[:10]:
        if url not in jobs:jobs[url]=await post('/jobs',{'url':url,'max_pages':max_pages,'max_chars':max_chars})
    results={url:await wait(job) for url,job in jobs.items()}
    return [results[url] for url in urls[:10]]
if __name__=='__main__':mcp.run(transport='stdio')
