import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from local_research.stack import ResearchStack, Settings


class RoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_full_output_does_not_silently_cap_at_40000(self):
        content = 'Public revenue evidence and historical records. ' * 3000
        self.stack.fetch = AsyncMock(return_value=(content.encode(), 'text/plain', 'https://example.org'))
        result = await self.stack.read('https://example.org', max_chars=0)
        self.assertEqual(result['text'], content)
        self.assertTrue(result['output_complete'])
        self.assertFalse(result['truncated'])

    async def test_requested_preview_marks_output_incomplete(self):
        content = 'Public revenue evidence and historical records. ' * 3000
        self.stack.fetch = AsyncMock(return_value=(content.encode(), 'text/plain', 'https://example.org'))
        result = await self.stack.read('https://example.org', max_chars=50000)
        self.assertEqual(len(result['text']), 50000)
        self.assertFalse(result['output_complete'])
        self.assertEqual(result['next_step'], 'Repeat with max_chars=0 for the complete selected page range.')

    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.stack = ResearchStack(Settings(state_dir=Path(self.temp.name), allow_local=True))

    async def asyncTearDown(self):
        await self.stack.close()
        self.temp.cleanup()

    async def test_empty_html_falls_back_and_success_is_cached(self):
        self.stack.fetch = AsyncMock(return_value=(b"<html><main id='app'></main></html>", "text/html", "https://example.org"))
        content = "Browser evidence about political interests and historical sources. " * 8
        self.stack.browser_read = AsyncMock(return_value=content)
        first = await self.stack.read("https://example.org")
        second = await self.stack.read("https://example.org")
        self.assertTrue(first["ok"])
        self.assertEqual(first["reader"], "crawl4ai")
        self.assertTrue(second["cache_hit"])
        self.assertEqual(self.stack.fetch.await_count, 1)
        self.assertEqual(self.stack.browser_read.await_count, 1)

    async def test_challenge_failure_not_cached_or_called_success(self):
        self.stack.fetch = AsyncMock(side_effect=RuntimeError("403"))
        self.stack.browser_read = AsyncMock(return_value="Verify you are human. " * 8)
        for _ in range(2):
            result = await self.stack.read("https://example.org")
            self.assertFalse(result["ok"])
            self.assertTrue(result["external_fallback_required"])
        self.assertEqual(self.stack.fetch.await_count, 2)

    async def test_digital_pdf_respects_page_range_and_skips_ocr(self):
        import pymupdf
        doc = pymupdf.open()
        for marker in ["FIRST", "SECOND", "THIRD"]:
            page = doc.new_page()
            page.insert_textbox(pymupdf.Rect(50, 50, 550, 700), marker + " source sentence. " * 20)
        data = doc.tobytes()
        doc.close()
        self.stack.fetch = AsyncMock(return_value=(data, "application/pdf", "https://example.org/file"))
        self.stack.ocr_read = AsyncMock()
        result = await self.stack.read("https://example.org/file", start_page=2, max_pages=1)
        self.assertTrue(result["ok"])
        self.assertEqual(result["pages_read"], [2, 2])
        self.assertIn("SECOND", result["text"])
        self.assertNotIn("FIRST", result["text"])
        self.assertNotIn("THIRD", result["text"])
        self.stack.ocr_read.assert_not_awaited()

    async def test_scanned_pdf_sends_only_requested_pages_to_ocr(self):
        import pymupdf
        doc = pymupdf.open()
        for _ in range(3):
            doc.new_page()
        data = doc.tobytes()
        doc.close()
        self.stack.fetch = AsyncMock(return_value=(data, "application/pdf", "https://example.org/scan"))
        async def ocr(path, engine):
            with pymupdf.open(path) as subset:
                self.assertEqual(len(subset), 1)
            return {"text": "OCR evidence from the requested page, with enough source text to read. " * 5,
                    "conversion_ms": 1, "cold": True, "engine": "docling-easyocr"}
        self.stack.ocr_read = AsyncMock(side_effect=ocr)
        result = await self.stack.read("https://example.org/scan", start_page=2, max_pages=1)
        self.assertTrue(result["ok"])
        self.assertEqual(result["reader"], "docling-easyocr")
        self.assertEqual(result["pages_read"], [2, 2])

    async def test_non_http_sources_rejected(self):
        result = await self.stack.read("file:///C:/Windows/win.ini")
        self.assertFalse(result["ok"])

    async def test_mixed_pdf_does_not_hide_scanned_page(self):
        import pymupdf
        doc = pymupdf.open()
        doc.new_page().insert_textbox(pymupdf.Rect(50, 50, 550, 700), "Digital source evidence. " * 20)
        doc.new_page()
        data = doc.tobytes()
        doc.close()
        self.stack.fetch = AsyncMock(return_value=(data, "application/pdf", "https://example.org/mixed"))
        async def ocr(path, engine):
            with pymupdf.open(path) as subset:
                self.assertEqual(len(subset), 1)
            return {"text": "Scanned page source evidence. " * 8, "conversion_ms": 1,
                    "cold": False, "engine": "pymupdf-tesseract"}
        self.stack.ocr_read = AsyncMock(side_effect=ocr)
        result = await self.stack.read("https://example.org/mixed", max_pages=2)
        self.assertTrue(result["ok"])
        self.assertEqual(result["ocr_pages"], [2])
        self.assertIn("Digital source", result["text"])
        self.assertIn("Scanned page", result["text"])

    async def test_scholarly_metadata_survives_article_extraction(self):
        html = b'<html><head><meta name="citation_author" content="Example Scholar"><meta name="citation_publication_date" content="1996"></head><body><article>' + b"Research evidence paragraph. " * 30 + b'</article></body></html>'
        self.stack.fetch = AsyncMock(return_value=(html, "text/html", "https://example.org/paper"))
        result = await self.stack.read("https://example.org/paper")
        self.assertTrue(result["ok"])
        self.assertIn("Example Scholar", result["text"])
        self.assertEqual(result["source_metadata"]["citation_publication_date"], ["1996"])

    async def test_search_cache_avoids_repeated_upstream_calls(self):
        import httpx
        self.stack.client.get = AsyncMock(return_value=httpx.Response(200, json={"results": [{"title": "Evidence", "url": "https://example.org"}]}, request=httpx.Request("GET", "http://localhost/search")))
        first = await self.stack.search("example evidence")
        second = await self.stack.search("example evidence")
        self.assertTrue(first["ok"])
        self.assertTrue(second["cache_hit"])
        self.assertEqual(self.stack.client.get.await_count, 1)

    async def test_rate_limited_empty_results_open_cooldown(self):
        import httpx
        self.stack.client.get = AsyncMock(return_value=httpx.Response(200, json={"results": [], "unresponsive_engines": [["brave", "too many requests"]]}, request=httpx.Request("GET", "http://localhost/search")))
        first = await self.stack.search("first")
        second = await self.stack.search("second")
        self.assertFalse(first["ok"])
        self.assertTrue(second["external_search_required"])
        self.assertIn("cooldown", second["error"].lower())
        self.assertEqual(self.stack.client.get.await_count, 1)

    async def test_router_uses_pdf_language_metadata_and_cache_policy(self):
        import pymupdf
        doc=pymupdf.open();doc.new_page();doc.xref_set_key(doc.pdf_catalog(),'Lang','(fr)')
        data=doc.tobytes();doc.close()
        self.stack.settings.ocr_service_url='http://127.0.0.1:8091'
        self.stack.fetch=AsyncMock(return_value=(data,'application/pdf','https://example.org/scanned'))
        self.stack.router_ocr=AsyncMock(return_value={'text':'Reliable source text. '*10,'engine':'router:rapidocr',
            'cold':False,'conversion_ms':1,'routes':[{'engine':'rapidocr'}]})
        result=await self.stack.read('https://example.org/scanned',cache=False)
        self.assertTrue(result['ok'])
        call=self.stack.router_ocr.call_args.args
        self.assertEqual(call[1:],('fr','balanced',False))

    async def test_fallback_completion_is_cached_without_charging_again(self):
        self.stack.fetch=AsyncMock(side_effect=RuntimeError('Network error'))
        self.stack.browser_read=AsyncMock(side_effect=RuntimeError('Browser failed'))
        first=await self.stack.read('https://example.org/source')
        self.assertTrue(first['external_fallback_required'])
        completed=await self.stack.complete_fallback(first['fallback_request_id'],'External source evidence. '*10,
            {'sourceURL':'https://example.org/source','statusCode':200},1)
        self.assertTrue(completed['ok'])
        second=await self.stack.read('https://example.org/source')
        self.assertTrue(second['cache_hit'])
        self.assertEqual(second['credits_used'],0)
        self.assertEqual(second['original_credits_used'],1)

    async def test_invalid_source_does_not_request_paid_fallback(self):
        result=await self.stack.read('file:///private.txt')
        self.assertFalse(result['external_fallback_required'])
        self.assertNotIn('fallback_request_id',result)

    async def test_sparse_browser_recovery_preserves_rendered_content(self):
        from types import SimpleNamespace
        self.stack.browser=SimpleNamespace(arun=AsyncMock(return_value=SimpleNamespace(
            success=False,status_code=200,error_message='Structural: no_content_elements',
            html='<html><body><main><div>Reliable historical evidence and records. The council met to discuss trade and taxation. Import duties were calculated on the market value of goods. A successful agreement required trust, money, and clear records.</div></main></body></html>')),close=AsyncMock())
        text=await self.stack.browser_read('https://example.org/app')
        self.assertIn('Reliable historical evidence',text)

    async def test_browser_recovery_rejects_http_failure(self):
        from types import SimpleNamespace
        self.stack.browser=SimpleNamespace(arun=AsyncMock(return_value=SimpleNamespace(
            success=False,status_code=403,error_message='Structural: no_content_elements',
            html='<main>'+('Reliable historical evidence. '*12)+'</main>')),close=AsyncMock())
        with self.assertRaises(RuntimeError):
            await self.stack.browser_read('https://example.org/app')

    async def test_read_many_deduplicates_identical_urls(self):
        self.stack.read=AsyncMock(return_value={'ok':True})
        result=await self.stack.read_many(['https://example.org/a','https://example.org/a'])
        self.assertEqual(len(result),2)
        self.assertEqual(self.stack.read.await_count,1)


if __name__ == "__main__":
    unittest.main()
