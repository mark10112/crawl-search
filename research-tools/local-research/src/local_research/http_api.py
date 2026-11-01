"""Persistent loopback HTTP adapter for reproducible retrieval timings and local clients."""
import asyncio
import os
import time
from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
import uvicorn

from .stack import ResearchStack

stack=None
semaphore=asyncio.Semaphore(3)


@asynccontextmanager
async def lifespan(app):
    global stack
    stack=ResearchStack()
    yield
    await stack.close()


async def read(request):
    start=time.perf_counter()
    try:
        args=await request.json()
        async with semaphore:
            result=await stack.read(**args)
        result['service_elapsed_ms']=round((time.perf_counter()-start)*1000,2)
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({'ok':False,'error':str(exc)},status_code=400)


async def health(request):
    return JSONResponse(await stack.health())


async def complete(request):
    try:
        args=await request.json()
        return JSONResponse(await stack.complete_fallback(**args))
    except Exception as exc:
        return JSONResponse({'ok':False,'error':str(exc)},status_code=400)


app=Starlette(routes=[Route('/read',read,methods=['POST']),Route('/complete',complete,methods=['POST']),
                      Route('/health',health)],lifespan=lifespan)

if __name__=='__main__':
    uvicorn.run(app,host='127.0.0.1',port=int(os.getenv('LOCAL_RESEARCH_PORT','8768')),log_level='warning')
