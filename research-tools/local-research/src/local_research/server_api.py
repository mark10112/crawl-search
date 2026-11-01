"""Loopback API with durable OCR jobs; reach it over SSH forwarding."""
import asyncio,contextlib,os
from contextlib import asynccontextmanager
from pathlib import Path
from starlette.applications import Starlette
from starlette.responses import JSONResponse,FileResponse
from starlette.routing import Route
import uvicorn
from .stack import ResearchStack,Settings
from .jobs import JobStore

stack=None;store=None;worker=None
ALLOWED={'url','upload_id','max_pages','start_page','max_chars','cache','ocr_engine','language_hint','ocr_policy','mode'}
def validate(args):
    if set(args)-ALLOWED:raise ValueError('Unsupported reader arguments')
    if bool(args.get('url'))==bool(args.get('upload_id')):raise ValueError('Provide exactly one URL or upload_id')
    return args
async def run_job(args):
    args=dict(args)
    if 'upload_id' in args:
        ident=args.pop('upload_id');store.asset(ident)
        local=ResearchStack(Settings(allow_local=True,state_dir=stack.settings.state_dir,ocr_service_url=stack.settings.ocr_service_url))
        try:
            result=await local.read(f'http://127.0.0.1:{os.getenv("LOCAL_RESEARCH_PORT","8768")}/assets/{ident}',**args)
            result.update(upload_id=ident,source_kind='uploaded-document')
            if result.get('external_fallback_required'):
                result['external_fallback_required']=False;result['needs_review']=True
                result.pop('next_tool_call',None)
                result['suggested_next_step']='This uploaded document has no public URL. Review it or explicitly authorise a separate cloud document upload.'
            return result
        finally:await local.close()
    return await stack.read(**args)
async def consume():
    while True:
        job=store.claim()
        if not job:await asyncio.sleep(.2);continue
        try:result=await run_job(job['arguments'])
        except Exception as exc:result={'ok':False,'error':str(exc)}
        result['server_commit']=os.getenv('RESEARCH_COMMIT','unknown');store.finish(job['id'],result)
@asynccontextmanager
async def lifespan(app):
    global stack,store,worker
    stack=ResearchStack();store=JobStore(Path(os.getenv('RESEARCH_JOBS_DIR',str(stack.settings.state_dir/'jobs'))));store.recover();worker=asyncio.create_task(consume())
    try:yield
    finally:
        worker.cancel()
        with contextlib.suppress(asyncio.CancelledError):await worker
        store.close();await stack.close()
async def guarded(fn):
    try:return JSONResponse(await fn())
    except Exception as exc:return JSONResponse({'ok':False,'error':str(exc)},status_code=400)
async def read(request):
    async def call():return await run_job(validate(await request.json()))
    return await guarded(call)
async def search(request):
    async def call():return await stack.search(**await request.json())
    return await guarded(call)
async def health(request):
    result=await stack.health();result.update(server='mac-research',commit=os.getenv('RESEARCH_COMMIT','unknown'),worker_alive=bool(worker and not worker.done()));return JSONResponse(result)
async def complete(request):
    async def call():return await stack.complete_fallback(**await request.json())
    return await guarded(call)
async def submit(request):
    async def call():return store.submit(validate(await request.json()))
    return await guarded(call)
async def status(request):
    result=store.get(request.path_params['ident']);return JSONResponse(result or {'error':'Unknown job'},status_code=200 if result else 404)
async def upload(request):
    parts=[];total=0
    async for part in request.stream():
        total+=len(part)
        if total>32*1024*1024:return JSONResponse({'error':'Upload exceeds 32 MiB'},status_code=413)
        parts.append(part)
    try:return JSONResponse(store.upload(b''.join(parts)))
    except ValueError as exc:return JSONResponse({'error':str(exc)},status_code=400)
async def asset(request):
    try:
        path=store.asset(request.path_params['ident'])
        with path.open('rb') as source:magic=source.read(8)
        media='application/pdf' if magic.startswith(b'%PDF') else 'image/png' if magic.startswith(b'\x89PNG') else 'image/jpeg' if magic.startswith(b'\xff\xd8') else 'image/tiff'
        return FileResponse(path,media_type=media)
    except ValueError:return JSONResponse({'error':'Unknown asset'},status_code=404)
app=Starlette(routes=[Route('/read',read,methods=['POST']),Route('/search',search,methods=['POST']),Route('/health',health),Route('/complete',complete,methods=['POST']),Route('/jobs',submit,methods=['POST']),Route('/jobs/{ident}',status),Route('/uploads',upload,methods=['POST']),Route('/assets/{ident}',asset)],lifespan=lifespan)
if __name__=='__main__':uvicorn.run(app,host='127.0.0.1',port=int(os.getenv('LOCAL_RESEARCH_PORT','8768')),log_level='warning')
