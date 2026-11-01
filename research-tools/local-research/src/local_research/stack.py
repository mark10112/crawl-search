from __future__ import annotations

import asyncio
import base64
import hashlib
import ipaddress
import json
import os
import socket
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import pymupdf
import trafilatura
from lxml import html as html_parser


def ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)


@dataclass
class Settings:
    searxng_url: str = field(default_factory=lambda: os.getenv("SEARXNG_URL", "http://127.0.0.1:8088"))
    state_dir: Path = field(default_factory=lambda: Path(os.getenv("LOCAL_RESEARCH_STATE", ".cache")))
    fetch_timeout: float = 15
    browser_timeout: float = 30
    ocr_timeout: float = field(default_factory=lambda: float(os.getenv('LOCAL_RESEARCH_OCR_TIMEOUT','180')))
    cache_seconds: int = 3600
    max_bytes: int = 32 * 1024 * 1024
    allow_local: bool = False  # Only enabled inside the controlled benchmark.
    ocr_service_url: str | None = field(default_factory=lambda: os.getenv("LOCAL_RESEARCH_OCR_URL"))


class ResearchStack:
    def __init__(self, settings: Settings | None = None):
        os.environ.setdefault("CRAWL4AI_NO_CLOUD_NOTICE", "1")
        self.settings = settings or Settings()
        self.settings.state_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.AsyncClient(timeout=self.settings.fetch_timeout, follow_redirects=False,
                                        headers={"User-Agent": "LocalResearch/0.1 (+local research reader)"})
        self.browser = None
        self.browser_lock = asyncio.Lock()
        self.ocr_lock = asyncio.Lock()
        self.ocr_process = None
        self.search_lock = asyncio.Lock()
        self.last_search = 0.0
        self.search_blocked_until = 0.0

    async def close(self):
        if self.browser:
            await self.browser.close()
        if self.ocr_process and self.ocr_process.returncode is None:
            self.ocr_process.terminate()
            await self.ocr_process.wait()
        await self.client.aclose()

    async def validate_url(self, url: str):
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
            raise ValueError("Only HTTP(S) URLs without embedded credentials are supported")
        if self.settings.allow_local:
            return
        addresses = await asyncio.get_running_loop().getaddrinfo(parts.hostname, parts.port or 443)
        if any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ValueError("Private/local source URLs are disabled")

    async def fetch(self, url: str):
        for _ in range(6):
            await self.validate_url(url)
            async with self.client.stream("GET", url) as response:
                if response.is_redirect:
                    url = str(response.url.join(response.headers["location"]))
                    continue
                response.raise_for_status()
                data = bytearray()
                async for part in response.aiter_bytes():
                    data.extend(part)
                    if len(data) > self.settings.max_bytes:
                        raise ValueError("Document exceeds the 32 MiB download limit")
                return bytes(data), response.headers.get("content-type", ""), str(response.url)
        raise ValueError("Too many redirects")

    async def search(self, query: str, limit: int = 5, cache: bool = True) -> dict:
        start = time.perf_counter()
        limit = max(1, min(limit, 10))
        key = hashlib.sha256(json.dumps([query.strip(), limit]).encode()).hexdigest()
        cached_path = self.settings.state_dir / ("search-" + key + ".json")
        if cache and cached_path.exists() and time.time() - cached_path.stat().st_mtime < 600:
            result = json.loads(cached_path.read_text(encoding="utf-8"))
            result.update(cache_hit=True, original_elapsed_ms=result["elapsed_ms"], elapsed_ms=ms(start))
            return result
        if time.monotonic() < self.search_blocked_until:
            return {"ok": False, "query": query, "results": [], "elapsed_ms": ms(start),
                    "external_search_required": True, "error": "Search cooldown after upstream rate limiting; use native search or wait.",
                    "retry_after_seconds": round(self.search_blocked_until-time.monotonic(), 1)}
        try:
            async with self.search_lock:
                if time.monotonic() < self.search_blocked_until:
                    return {"ok": False, "query": query, "results": [], "elapsed_ms": ms(start),
                            "external_search_required": True, "error": "Search cooldown; use native search or wait."}
                await asyncio.sleep(max(0, 1.0 - (time.monotonic() - self.last_search)))
                response = await self.client.get(self.settings.searxng_url.rstrip("/") + "/search",
                                                 params={"q": query, "format": "json"})
                self.last_search = time.monotonic()
            response.raise_for_status()
            payload = response.json()
            results = payload.get("results", [])[:limit]
            result = {"ok": bool(results), "query": query, "elapsed_ms": ms(start), "cache_hit": False,
                    "results": [{"title": r.get("title"), "url": r.get("url"),
                                 "snippet": r.get("content"), "engines": r.get("engines", [])}
                                for r in results],
                    "engine_errors": payload.get("unresponsive_engines", []),
                    "external_search_required": not bool(results),
                    "suggested_next_step": None if results else "Try a broader query or the agent's native web search; no paid search was called."}
            if not results and any("too many" in str(error).lower() or "captcha" in str(error).lower()
                                   for error in payload.get("unresponsive_engines", [])):
                self.search_blocked_until = time.monotonic() + 60
            if cache and results:
                temporary = cached_path.with_suffix(".tmp")
                temporary.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
                temporary.replace(cached_path)
            return result
        except Exception as exc:
            return {"ok": False, "query": query, "elapsed_ms": ms(start), "error": str(exc),
                    "external_search_required": True}

    @staticmethod
    def usable(text: str) -> bool:
        text = text.strip()
        blocked = ("just a moment", "verify you are human", "access denied", "enable javascript and cookies",
                   "checking your browser", "attention required!", "captcha")
        return len(text) >= 100 and not (len(text) < 2000 and any(x in text.lower() for x in blocked))

    @staticmethod
    def source_metadata(data: bytes) -> dict:
        """Keep scholarly metadata that article-body extractors commonly discard."""
        metadata = {}
        try:
            tree = html_parser.fromstring(data)
            for tag in tree.xpath("//meta[@content]"):
                name = (tag.get("name") or tag.get("property") or "").lower()
                if name.startswith(("citation_", "dc.", "dcterms.")) or name in {"article:published_time", "og:title"}:
                    metadata.setdefault(name, []).append(tag.get("content"))
        except (ValueError, TypeError):
            pass
        return metadata

    async def browser_read(self, url: str) -> str:
        async with self.browser_lock:
            if self.browser is None:
                # Crawl4AI logs must never corrupt MCP's stdout protocol.
                import contextlib
                with contextlib.redirect_stdout(sys.stderr):
                    from crawl4ai import AsyncWebCrawler, BrowserConfig
                    self.browser = AsyncWebCrawler(config=BrowserConfig(headless=True, verbose=False))
                    await self.browser.start()
            from crawl4ai import CrawlerRunConfig, CacheMode
            result = await self.browser.arun(url=url, config=CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS, verbose=False,
                page_timeout=int(self.settings.browser_timeout * 1000), delay_before_return_html=0.5))
            if not result.success:
                # Sparse JS applications can contain valid rendered div/main text
                # without the article/p tags expected by Crawl4AI's structural gate.
                # Never recover known challenge/block signatures or HTTP failures.
                structural='Structural: no_content_elements' in (result.error_message or '')
                recovered=trafilatura.extract(result.html or '',output_format='markdown',include_comments=False) or ''
                if structural and result.status_code==200 and self.usable(recovered):
                    return recovered
                raise RuntimeError(result.error_message or "Browser read failed")
            if result.status_code and result.status_code >= 400:
                raise RuntimeError(f"Browser HTTP {result.status_code}")
            markdown = result.markdown
            return markdown.raw_markdown if hasattr(markdown, "raw_markdown") else str(markdown or "")

    async def ocr_read(self, path: Path, engine: str = "auto") -> dict:
        async with self.ocr_lock:
            if self.ocr_process is None or self.ocr_process.returncode is not None:
                self.ocr_process = await asyncio.create_subprocess_exec(
                    sys.executable, "-u", "-m", "local_research.ocr_worker",
                    stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                    # Model logs/download messages go to stderr, not the protocol.
                    stderr=None, env={**os.environ, "TOKENIZERS_PARALLELISM": "false"})
            self.ocr_process.stdin.write((json.dumps({"path": str(path.resolve()), "engine": engine}) + "\n").encode())
            await self.ocr_process.stdin.drain()
            try:
                line = await asyncio.wait_for(self.ocr_process.stdout.readline(), self.settings.ocr_timeout)
                if not line:
                    raise RuntimeError("OCR worker stopped without a response")
                result = json.loads(line)
                if not result.get("ok"):
                    raise RuntimeError(result.get("error", "OCR conversion failed"))
                return result
            except (TimeoutError, json.JSONDecodeError):
                self.ocr_process.kill()
                await self.ocr_process.wait()
                raise RuntimeError("OCR timed out or returned an invalid response; worker restarted on next use")

    async def router_ocr(self, data: bytes, language_hint: str | None, policy: str, cache: bool) -> dict:
        if not self.settings.ocr_service_url:
            raise RuntimeError("OCR router service is not configured")
        images=[]
        if data.startswith(b"%PDF"):
            with pymupdf.open(stream=data,filetype="pdf") as doc:
                images=[page.get_pixmap(dpi=144,alpha=False).tobytes("png") for page in doc]
        else:
            images=[data]
        texts=[]
        routes=[]
        for number,image in enumerate(images,1):
            response=await self.client.post(self.settings.ocr_service_url.rstrip('/')+'/ocr',json={
                'image_base64':base64.b64encode(image).decode(), 'language_hint':language_hint,
                'policy':policy,'cache':cache},timeout=self.settings.ocr_timeout)
            response.raise_for_status()
            result=response.json()
            if not result.get('ok'):
                raise RuntimeError(result.get('error','OCR router returned unusable text'))
            texts.append(f'<!-- subset page {number} -->\n'+result['text'])
            routes.append({k:result.get(k) for k in ['engine','revision','route','cache_hit','policy','language_hint','elapsed_ms','quality_warning']})
        return {'text':'\n\n'.join(texts),'engine':'router:'+','.join(dict.fromkeys(r['engine'] for r in routes)),
                'cold':False,'conversion_ms':sum(r['elapsed_ms'] for r in routes),'routes':routes}

    async def read(self, url: str, *, mode: str = "auto", cache: bool = True,
                   max_chars: int = 22000, max_pages: int = 5, start_page: int = 1,
                   ocr_engine: str = "auto", language_hint: str | None = None,
                   ocr_policy: str = "balanced") -> dict:
        if mode not in {"auto", "basic", "browser", "ocr"}:
            raise ValueError("mode must be auto/basic/browser/ocr")
        if ocr_engine not in {"auto", "tesseract", "docling", "router"}:
            raise ValueError("ocr_engine must be auto/tesseract/docling/router")
        if ocr_policy not in {"balanced","quality"}:
            raise ValueError("ocr_policy must be balanced or quality")
        max_chars = max(100, min(max_chars, 40000))
        max_pages = max(1, min(max_pages, 10))
        start_page = max(1, start_page)
        start = time.perf_counter()
        key = hashlib.sha256(json.dumps(["reader-v5-explicit-ocr-budget", url, mode, max_chars, max_pages, start_page, ocr_engine,language_hint,ocr_policy]).encode()).hexdigest()
        cached_path = self.settings.state_dir / (key + ".json")
        if cache and cached_path.exists() and time.time() - cached_path.stat().st_mtime < self.settings.cache_seconds:
            result = json.loads(cached_path.read_text(encoding="utf-8"))
            result.update(cache_hit=True, original_elapsed_ms=result["elapsed_ms"], elapsed_ms=ms(start), stages=[],
                          original_fallback_count=result.get("fallback_count", 0), fallback_count=0,
                          original_credits_used=result.get('credits_used',0),credits_used=0)
            return result
        stages = []
        result = {"ok": False, "url": url, "reader": None, "cache_hit": False,
                  "stages": stages, "text": "", "external_fallback_required": False,'credits_used':0}
        source_allowed=False
        async def stage(name, operation):
            clock = time.perf_counter()
            try:
                value = await operation
                stages.append({"name": name, "ok": True, "elapsed_ms": ms(clock)})
                return value
            except Exception as exc:
                stages.append({"name": name, "ok": False, "elapsed_ms": ms(clock), "error": str(exc)[:700]})
                raise
        try:
            await self.validate_url(url)
            source_allowed=True
            data = None
            if mode == "browser":
                text = await stage("browser", self.browser_read(url))
                result["reader"] = "crawl4ai"
            else:
                try:
                    data, content_type, final_url = await stage("fetch", self.fetch(url))
                    result["final_url"] = final_url
                    result['content_sha256']=hashlib.sha256(data).hexdigest()
                except Exception:
                    if mode != "auto" or urlsplit(url).path.lower().endswith(".pdf"):
                        raise
                    text = await stage("browser", self.browser_read(url))
                    result["reader"] = "crawl4ai"
                if data is not None:
                    if content_type.startswith('image/'):
                        ocr=await stage('ocr-router',self.router_ocr(data,language_hint,ocr_policy,cache))
                        text=ocr['text']
                        result.update(reader=ocr['engine'],ocr_routes=ocr['routes'],ocr_warning='OCR completion checks are not proof of transcription accuracy; verify against the image.')
                    elif data.startswith(b"%PDF") or "application/pdf" in content_type:
                        parse_start = time.perf_counter()
                        with pymupdf.open(stream=data, filetype="pdf") as pdf:
                            declared_language=pdf.xref_get_key(pdf.pdf_catalog(),'Lang')
                            document_hint=language_hint or (declared_language[1] if declared_language[0]=='string' else None)
                            result['document_language_hint']=document_hint
                            if start_page > len(pdf):
                                raise ValueError("start_page exceeds PDF length")
                            end_page = min(len(pdf), start_page + max_pages - 1)
                            result.update(total_pages=len(pdf), pages_read=[start_page, end_page])
                            page_texts = {p: pdf[p].get_text() for p in range(start_page - 1, end_page)}
                            text = "\n\n".join(f"<!-- page {p+1} -->\n" + page_text
                                                for p, page_text in page_texts.items())
                            result["reader"] = "pdf-text"
                            # A digital first page must not hide a scanned second page.
                            ocr_pages = [p for p, value in page_texts.items() if mode == "ocr" or not self.usable(value)]
                            needs_ocr = bool(ocr_pages)
                            if needs_ocr and mode != "basic":
                                subset = pymupdf.open()
                                for p in ocr_pages:
                                    subset.insert_pdf(pdf, from_page=p, to_page=p)
                                result["ocr_pages"] = [p + 1 for p in ocr_pages]
                                subset_path = self.settings.state_dir / (key + ".pdf")
                                subset.save(subset_path)
                                subset.close()
                        stages.append({"name": "pdf-text", "ok": True, "elapsed_ms": ms(parse_start),
                                       "needs_ocr": needs_ocr})
                        if needs_ocr and mode != "basic":
                            if ocr_engine=='router' or (ocr_engine=='auto' and self.settings.ocr_service_url):
                                ocr=await stage('ocr-router',self.router_ocr(subset_path.read_bytes(),document_hint,ocr_policy,cache))
                                result['ocr_routes']=ocr['routes']
                            else:
                                ocr = await stage("ocr", self.ocr_read(subset_path, ocr_engine))
                            digital_text = "\n\n".join(f"<!-- page {p+1} -->\n" + value
                                                        for p, value in page_texts.items() if p not in ocr_pages)
                            text = digital_text + "\n\n" + ocr["text"]
                            result.update(reader=ocr["engine"], ocr_conversion_ms=ocr["conversion_ms"],
                                          ocr_cold=ocr["cold"], fast_ocr_error=ocr.get("fast_ocr_error"),
                                          ocr_warning="OCR subset page numbers map in order to ocr_pages. OCR may misread names, dates and Thai text; verify against page images.")
                    else:
                        if mode == "ocr":
                            raise ValueError("OCR mode requires a PDF URL")
                        parse_start = time.perf_counter()
                        if "text/plain" in content_type:
                            text = data.decode("utf-8", errors="replace")
                        else:
                            text = await asyncio.to_thread(trafilatura.extract, data, output_format="markdown",
                                                           include_tables=True, include_comments=False)
                            result["source_metadata"] = self.source_metadata(data)
                        text = text or ""
                        result["reader"] = "http-trafilatura"
                        stages.append({"name": "extract", "ok": self.usable(text), "elapsed_ms": ms(parse_start)})
                        if not self.usable(text) and mode == "auto":
                            text = await stage("browser", self.browser_read(result.get("final_url", url)))
                            result["reader"] = "crawl4ai"
                        if result.get("source_metadata"):
                            text = "## Source metadata (HTML meta tags)\n" + "\n".join(
                                f"- {name}: {'; '.join(values)}" for name, values in result["source_metadata"].items()) + "\n\n" + text
            result["ok"] = self.usable(text)
            if mode == "basic" and result.get("reader") == "pdf-text" and needs_ocr:
                result["ok"] = False
                result["incomplete_pages"] = [p + 1 for p in ocr_pages]
            result.update(text=text[:max_chars], extracted_chars=len(text), truncated=len(text) > max_chars)
            if not result["ok"]:
                result["error"] = "No usable article text; do not treat an empty/challenge page as evidence"
        except Exception as exc:
            result["error"] = str(exc)[:900]
        result.update(elapsed_ms=ms(start), fallback_count=sum(s["name"] in {"browser", "ocr",'ocr-router'} for s in stages))
        result["external_fallback_required"] = not result["ok"]
        if not source_allowed:
            result['external_fallback_required']=False
            return result
        if not result["ok"]:
            request_id=uuid.uuid4().hex
            pending={'id':request_id,'cache_key':key,'cache':cache,'url':url,'max_pages':max_pages,
                     'max_chars':max_chars,'created_at':time.time(),'local_result':result}
            (self.settings.state_dir/('pending-'+request_id+'.json')).write_text(json.dumps(pending,ensure_ascii=False),encoding='utf-8')
            result.update(fallback_request_id=request_id, next_tool_call={'server':'firecrawl','tool':'firecrawl_scrape',
                'arguments':{'url':url,'formats':['markdown'],'maxAge':3600000 if cache else 0,
                             'storeInCache':cache,'pdfOptions':{'maxPages':max_pages},'domainTools':False}},
                suggested_next_step='Use the connected Firecrawl tool once within the authorized credit budget, then research_complete_fallback; do not repeat indefinitely.')
        if cache and result["ok"]:
            temp = cached_path.with_suffix(".tmp")
            temp.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            temp.replace(cached_path)
        return result

    async def complete_fallback(self, request_id: str, text: str, metadata: dict, credits_used: int | None) -> dict:
        if len(request_id)!=32 or any(c not in '0123456789abcdef' for c in request_id):
            raise ValueError('Invalid fallback request id')
        path=self.settings.state_dir/('pending-'+request_id+'.json')
        pending=json.loads(path.read_text(encoding='utf-8'))
        if time.time()-pending['created_at']>3600:
            raise ValueError('Fallback request expired')
        if metadata.get('statusCode',200)>=400:
            raise ValueError('External source returned an error status')
        if metadata.get('sourceURL') and metadata['sourceURL']!=pending['url']:
            raise ValueError('External source URL does not match pending request')
        if credits_used is not None and credits_used<0:
            raise ValueError('Credit usage must not be negative')
        if metadata.get('numPages',0)>pending['max_pages']:
            raise ValueError('External reader exceeded the requested page bound')
        result={**pending['local_result'],'ok':self.usable(text),'reader':'firecrawl-fallback',
                'text':text[:pending['max_chars']],'external_metadata':metadata,'credits_used':credits_used,
                'external_fallback_required':False,'fallback_request_id':request_id,
                'cache_hit':False,'fallback_count':pending['local_result'].get('fallback_count',0)+1,
                'elapsed_ms':round((time.time()-pending['created_at'])*1000+pending['local_result']['elapsed_ms'],2)}
        if result['ok']:
            result.pop('error',None)
        if pending['cache'] and result['ok']:
            target=self.settings.state_dir/(pending['cache_key']+'.json')
            target.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
        return result

    async def read_many(self, urls: list[str], **kwargs):
        semaphore = asyncio.Semaphore(3)
        async def one(url):
            async with semaphore:
                return await self.read(url, **kwargs)
        tasks={url:asyncio.create_task(one(url)) for url in dict.fromkeys(urls[:10])}
        return await asyncio.gather(*(tasks[url] for url in urls[:10]))

    async def health(self):
        from importlib.metadata import version, PackageNotFoundError
        packages = {}
        for name in ["local-research-stack", "crawl4ai", "docling", "easyocr", "torch", "mcp"]:
            try:
                packages[name] = version(name)
            except PackageNotFoundError:
                packages[name] = "not installed"
        try:
            response = await self.client.get(self.settings.searxng_url + "/")
            status = response.status_code
        except Exception as exc:
            status = str(exc)
        router_health=None
        if self.settings.ocr_service_url:
            try:
                router_health=(await self.client.get(self.settings.ocr_service_url.rstrip('/')+'/health')).json()
            except Exception as exc:
                router_health={'ok':False,'error':str(exc)}
        return {"searxng": status, "packages": packages, "browser_started": self.browser is not None,
                "ocr_started": self.ocr_process is not None,'ocr_router':router_health,
                "paid_fallback": "connected-client-agent-handoff"}
