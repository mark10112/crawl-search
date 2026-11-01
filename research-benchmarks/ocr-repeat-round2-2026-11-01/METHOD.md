# Round 2 frozen protocol

Before: round 1 explicit 8192-token worker and reader at 27466cae9c17ab3427295d0c64cc1b93556e551c. After: frozen candidate commit recorded by driver. Both native PaddleOCR-VL-1.6/MLX on the same Mac M4. No main deployment, no Firecrawl.

Changes: repetition_penalty=1.05, context=64, max_new_tokens=8192 retained; presentation-only HTML table attributes removed preserving cells, spans and all text; API supports max_chars=0 for complete selected pages and labels positive previews output_complete=false. No completion checks relaxed. No deleting repeated output. No retry or reference-dependent logic.

Primary A/B: same four source PDFs, three pages each, hashes from original manifest; same frozen 24 span/15 row reference set and scoring. Sequential before/after; each variant restarts MLX and uses identical English warmup; auto then forced OCR, original manifest order. All read/page result caches disabled. Each reader uses its matching source; identical request max_chars=40000 (not a change to scoring budget), 3 pages. Full selected output is accepted only if reader ok, no API truncation and all observed pages finish normally. Keep rejected and partial outputs. Single A/B observations, not statistical evidence.

Capture wire penalties, completion budgets and reasons; raw page provenance, native process RSS and host memory at 0.5 s. Times exclude upload, include local async job polling. RSS is not total unified GPU allocation. Production admission drained and original OCR worker paused; all supervisors restored by finally.

Acceptance: increase complete delivered document count, retain or improve comparable sampled CER/strict rows, no unexplained drop in page/region coverage. Do not merge main automatically even if results improve; preserve reviewable evidence.
