# Mac activation validation — 2026-11-01

This records service migration, not a new Firecrawl accuracy/performance benchmark. The core end-to-end runs used `e54eac1735ade24dd6875a612991375bca652d19`; subsequent changes route the legacy synchronous `/read` endpoint through the same queue and add documentation.

| Check | Observed result |
|---|---|
| Windows research containers | `local-research-ocr`, `searxng-local`: exited, restart=no; old research ports not listening |
| Mac services | SearXNG + native reader + Paddle layout/MLX OCR running; loopback only |
| Windows and Mac unit checks | 21/21 on each machine |
| MCP tool discovery | Eight remote tools |
| SearXNG search | Three results in 0.906 s; DuckDuckGo CAPTCHA retained in engine_errors |
| HTTP document | SearXNG official search API page, 1.094 s uncached |
| JavaScript document | quotes.toscrape.com/js/, actual Crawl4AI browser, 6.500 s |
| Thai PNG | Native Paddle/MLX, 8.594 s uncached; includes an extraneous Chinese fragment |
| Two-page digital PDF | 0.593 s; pages 1–2, expected text and SHA-256 verified |
| Duplicate URL reads | Same persistent job ID returned twice |
| MCP reconnect | Completed PDF retrievable after tunnel/client shutdown and fresh session |
| Gateway restart | Completed Thai result unchanged after `launchctl kickstart -k` |
| Real Census table image | 49.407 s; failed normal-finish gate, needs_review=true, credits=0 |

The real table is [Census Bulletin 21 (1900), page 2](https://www2.census.gov/library/publications/decennial/1900/bulletins/demographic/21-population-il.pdf). The other image fixtures and their ground truth are in the existing multilingual dataset. No character-error score is asserted for these smoke tests. The failure gate is useful but cannot detect all wrong characters or hallucinations.

Raw activation results are retained outside Git on the client under `research-benchmarks/ocr-model-research-2026-11-01/migration/` (`client-smoke-final.json`, `document-smoke.json`) and on Mac in `~/research-server/validation/`. They can include local upload IDs and runtime details. Model weights, SSH keys, generated server secrets and runtime state are not committed.

Full restart/login recovery, peak-memory/load tests, long-document accuracy and a fresh same-corpus Firecrawl comparison remain unmeasured. Active services are per-user LaunchAgents and require a logged-in Mac session.
