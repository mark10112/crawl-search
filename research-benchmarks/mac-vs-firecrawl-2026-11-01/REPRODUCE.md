# Reproduce this run

Use the four exact excerpts from the original `real-history-2026-11-01` manifest. The activated Mac has these in the verified staged migration release. The fixture server exposes only those PDFs, not this repository or reference text.

1. Keep the model/service configuration unchanged from the recorded run. Start with a loaded recognition model. Check production health and an empty queue. Save the deployed Git commit and OCR dependency versions.
2. On Mac set `MAC_BENCH_WORK` to a **fresh absolute directory** for a new run. Run `start_mac.py` with the reader environment. It starts an isolated API on 8778, four-file server on 8877, temporary cloudflared tunnel and memory sampler. It refuses to reuse an existing process manifest. Keep the printed URL/config.
3. Check all four public URLs return the expected SHA-256 before measurements. Snapshot account usage via connected Firecrawl, not a key copied to Mac.
4. Call connected `firecrawl_scrape` sequentially for each file in each phase, preserving the exact `request` objects in the recorded Firecrawl JSON. Off: maxAge=0/storeInCache=false; prime: maxAge=0/storeInCache=true; hit: maxAge=3600000/storeInCache=true. Use the new public base URL. Record wall time to the complete tool result, raw structured data, billing metadata, cache state and feedback receipts. Do not replace failure records with retries. Twelve calls maximum, physically three pages each.
5. Launch `run_mac.py WORK_DIRECTORY PUBLIC_BASE_URL` with the reader environment. It records off/prime/hit and the additional forced-quality off run. Models stay loaded, background applications stay as observed. Do not install packages or run extra GPU jobs on Mac during collection.
6. Wait for `mac-done.json`. Run `collect_mac.py` with the OCR environment and the same `MAC_BENCH_WORK`. It validates that jobs have ended, checks PID commands, stops only the four temporary processes, captures backend completion evidence and checks production health.
7. Copy `WORK_DIRECTORY/results/*` alongside the saved Firecrawl results. Keep account balance snapshots in a private `.cache/` directory. Install `metrics-requirements.txt` into a separate `.deps/` target and run `analyze.py`, `report.py`, `plot.py`. Keep prior evidence; write a new report/run folder instead of overwriting it.

The source-image references must remain unchanged. `reference-lock.json` records Windows CRLF, Mac LF and canonical JSON hashes. Scoring asserts the canonical hash, avoiding newline-only differences. Twenty-eight results are expected: 12 main Mac + 4 forced OCR + 12 Firecrawl; sixteen Mac hashes must match the corpus manifest.

This uses native Mac processes rather than hard RAM isolation, and cloud server RAM cannot be observed. The report generator describes this recorded run's observed cache/failure behavior; inspect and rewrite its narrative against any new run instead of blindly reusing its conclusions.
