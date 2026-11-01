"""Repeatable transport/extraction benchmark. Does not measure model answer quality."""
from __future__ import annotations

import argparse
import asyncio
import functools
import http.server
import json
import math
import platform
import statistics
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil
import pymupdf
from PIL import Image, ImageDraw, ImageFont

from .stack import ResearchStack, Settings


QUERIES = ["Front Palace crisis 1874 1875 Knox Clarke Wichaichan",
           '"การวิเคราะห์ในเชิงประวัติศาสตร์" "วังหน้า"',
           "Bowring treaty 1855 article VIII three per cent export",
           "site:docs.searxng.org search API 403 formats json",
           "site:github.com/ihor-sokoliuk/mcp-searxng/releases latest",
           "วิกฤตการณ์วังหน้า วางเพลิง หลักฐาน"]
LIVE = [
    ("treaty", "https://worldjpn.net/documents/texts/docs/18550418.T1E.html", ["ARTICLE VIII", "Opium"]),
    ("api-docs", "https://docs.searxng.org/dev/search_api.html", ["403", "format"]),
    ("journal", "https://so04.tci-thaijo.org/index.php/kjss/article/view/243645", ["Kapilakanchana", "27"]),
    ("archives", "https://www.nationalarchives.gov.uk/explore-the-collection/stories/britains-role-in-the-front-palace-crisis/", ["Clarke", "1875"]),
    ("release", "https://github.com/ihor-sokoliuk/mcp-searxng/releases", ["v2.9.0", "pages"]),
]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def fixtures(folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    body = ("<h1>Controlled research source</h1><p>RESEARCH_MARKER_1874. "
            "This is a controlled source with known content for testing successful extraction. "
            "A fast response without this evidence is not a successful read. "
            "The source describes a political negotiation, money and competing interests.</p>" * 3)
    (folder / "plain.html").write_text("<!doctype html><html><body><article>" + body + "</article></body></html>", encoding="utf-8")
    (folder / "dynamic.html").write_text(
        '<!doctype html><html><body><main id="app"></main><script>setTimeout(()=>{document.getElementById("app").innerHTML='
        + json.dumps(body) + '}, 100);</script></body></html>', encoding="utf-8")
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_textbox(pymupdf.Rect(50, 50, 550, 700),
                        "PDF_TEXT_MARKER_1855\n" + "A known digital PDF source with money, law and political negotiations. " * 6,
                        fontsize=14)
    pdf.save(folder / "digital.pdf")
    pdf.close()
    image = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(image)
    font_path = Path("C:/Windows/Fonts/LeelawUI.ttf")
    if not font_path.exists():
        font_path = Path("C:/Windows/Fonts/arial.ttf")
    font = ImageFont.truetype(str(font_path), 38)
    lines = ["LOCAL RESEARCH OCR TEST 1874", "This page is a scanned image, not selectable text.",
             "The first task is to read evidence before making a claim.",
             "A successful result must contain these source sentences.",
             "เอกสารทดสอบภาษาไทย วังหน้าและการเมือง", "ตรวจสอบหลักฐานก่อนสรุปเหตุการณ์", "เงิน อำนาจ และการเจรจา"]
    for index, line in enumerate(lines):
        draw.text((70, 120 + index * 100), line, font=font, fill="black")
    image.save(folder / "scanned.png")
    scan = pymupdf.open()
    page = scan.new_page(width=620, height=877)
    page.insert_image(page.rect, filename=str(folder / "scanned.png"))
    scan.save(folder / "scanned.pdf")
    scan.close()


def percentile(values, quantile):
    return round(sorted(values)[max(0, math.ceil(len(values) * quantile) - 1)], 2)


def summarize(rows):
    groups = {}
    for row in rows:
        key = f'{row["suite"]}/{row["case"]}/{row["mode"]}/{row["phase"]}'
        groups.setdefault(key, []).append(row)
    output = []
    for key, entries in groups.items():
        times = [entry["elapsed_ms"] for entry in entries]
        output.append({"group": key, "n": len(entries), "successes": sum(e["verified"] for e in entries),
                       "p50_ms": round(statistics.median(times), 2), "p95_ms": percentile(times, .95),
                       "max_ms": max(times), "fallbacks": sum(e.get("fallback_count", 0) for e in entries)})
    return output


class ResourceSampler:
    def __init__(self):
        self.stop_event = threading.Event()
        self.peak_rss = 0
        self.thread = threading.Thread(target=self.sample, daemon=True)

    def sample(self):
        root = psutil.Process()
        while not self.stop_event.is_set():
            total = 0
            for process in [root, *root.children(recursive=True)]:
                try:
                    total += process.memory_info().rss
                except psutil.Error:
                    pass
            self.peak_rss = max(self.peak_rss, total)
            self.stop_event.wait(.1)


async def benchmark(args):
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    fixture_dir = output / "fixtures"
    fixtures(fixture_dir)
    handler = functools.partial(QuietHandler, directory=str(fixture_dir.resolve()))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    settings = Settings(state_dir=output / "cache", allow_local=True, ocr_timeout=args.ocr_timeout)
    stack = ResearchStack(settings)
    rows = []
    sampler = ResourceSampler()
    sampler.thread.start()
    metadata = {"started": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
                "logical_cpus": psutil.cpu_count(), "system_ram_bytes": psutil.virtual_memory().total,
                "repeats": args.repeats, "health": await stack.health(),
                "notes": ["No model generation or paid tools; HTTP/extraction/OCR only.",
                          "Warm measurements bypass result caches; cached phase is separate.",
                          "p95 is nearest-rank; small n is descriptive, not statistically conclusive.",
                          "Peak RSS sums process working sets; shared pages may be double-counted; Docker SearXNG excluded."]}
    def record(suite, case, mode, phase, result, anchors):
        text = result.get("text", "")
        # Markdown escapes are formatting, not a missing evidence marker.
        normalized = text.replace("\\_", "_").lower()
        verified = result.get("ok", False) and all(a.lower() in normalized for a in anchors)
        row = {"suite": suite, "case": case, "mode": mode, "phase": phase, "verified": verified, **result}
        if "OCR" in case:
            compact = "".join(text.split())
            row["thai_anchors"] = {a: a in compact for a in ["ภาษาไทย", "วังหน้า", "หลักฐาน"]}
            row["english_anchors"] = {a: a.lower() in normalized for a in ["LOCAL RESEARCH OCR TEST", "scanned image", "first task", "successful result"]}
            row["verified"] = row["verified"] and all(row["thai_anchors"].values()) and all(row["english_anchors"].values())
        rows.append(row)
        (output / "raw.json").write_text(json.dumps({"metadata": metadata, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({k: row.get(k) for k in ["suite", "case", "mode", "phase", "verified", "elapsed_ms", "reader", "error"]}, ensure_ascii=False), flush=True)
    try:
        if args.suite in {"controlled", "all"}:
            cases = [("plain", "plain.html", ["RESEARCH_MARKER_1874"]),
                     ("JavaScript", "dynamic.html", ["RESEARCH_MARKER_1874"]),
                     ("digital-PDF", "digital.pdf", ["PDF_TEXT_MARKER_1855"]),
                     ("scanned-OCR", "scanned.pdf", ["LOCAL RESEARCH OCR TEST", "1874"])]
            for name, path, anchors in cases:
                url = base + "/" + path
                for mode in ["basic", "auto"]:
                    result = await stack.read(url, mode=mode, cache=False, max_pages=1)
                    record("controlled", name, mode, "first", result, anchors)
                    for _ in range(args.repeats):
                        result = await stack.read(url, mode=mode, cache=False, max_pages=1)
                        record("controlled", name, mode, "warm", result, anchors)
                    # Populate cache separately, then measure only verified cached reads.
                    populated = await stack.read(url, mode=mode, cache=True, max_pages=1)
                    if populated["ok"]:
                        for _ in range(args.repeats):
                            record("controlled", name, mode, "cached", await stack.read(url, mode=mode, cache=True, max_pages=1), anchors)
            urls = [base + "/plain.html", base + "/dynamic.html", base + "/digital.pdf"]
            for strategy in ["sequential", "parallel"]:
                for _ in range(args.repeats):
                    start = time.perf_counter()
                    results = ([await stack.read(url, cache=False) for url in urls] if strategy == "sequential"
                               else await stack.read_many(urls, cache=False))
                    rows.append({"suite": "batch", "case": "three-independent-URLs", "mode": strategy,
                                 "phase": "warm", "elapsed_ms": round((time.perf_counter()-start)*1000, 2),
                                 "verified": all(r["ok"] for r in results), "results": results})
        if args.suite in {"live", "all"}:
            for name, url, anchors in LIVE:
                for repeat in range(args.repeats):
                    # Alternate order to reduce a constant first-reader advantage.
                    for mode in (["basic", "auto"] if repeat % 2 == 0 else ["auto", "basic"]):
                        record("live", name, mode, "uncached", await stack.read(url, mode=mode, cache=False), anchors)
            for query in QUERIES:
                for _ in range(args.repeats):
                    result = await stack.search(query, 5, cache=False)
                    rows.append({"suite": "search", "case": query, "mode": "searxng", "phase": "upstream-cache-uncontrolled",
                                 "verified": result.get("ok", False) and bool(result.get("results")), **result})
            if args.real_pdf:
                url = "https://so04.tci-thaijo.org/index.php/kjss/article/download/243645/165556"
                for mode in ["basic", "auto"]:
                    record("live", "Thai-scanned-PDF-first-two-pages", mode, "uncached",
                           await stack.read(url, mode=mode, cache=False, max_pages=2), ["วังหน้า"])
    finally:
        await stack.close()
        server.shutdown()
        sampler.stop_event.set()
        sampler.thread.join()
    metadata.update(finished=datetime.now(timezone.utc).isoformat(), peak_process_tree_rss_bytes=sampler.peak_rss)
    summary = summarize(rows)
    (output / "raw.json").write_text(json.dumps({"metadata": metadata, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Performance measurements", "", "No model generation or paid tools. See raw.json for full texts, stage timings, errors and metadata.", "",
             "| Group | n | Verified | p50 ms | p95 ms | Fallbacks |", "|---|---:|---:|---:|---:|---:|"]
    for row in summary:
        lines.append(f'| {row["group"]} | {row["n"]} | {row["successes"]}/{row["n"]} | {row["p50_ms"]} | {row["p95_ms"]} | {row["fallbacks"]} |')
    lines += ["", f'Peak summed process-tree RSS: {sampler.peak_rss / 1024**3:.2f} GiB (shared pages may be counted twice; excludes Docker).',
              "", "First request may include model download, import and initialization. Warm bypasses result caches. Cached is a separate mode.",
              "Do not compare against earlier agent wall times: these measurements exclude model reasoning and answer composition."]
    (output / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"output": str(output.resolve()), "rows": len(rows), "peak_rss_gib": round(sampler.peak_rss/1024**3, 2)}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=["controlled", "live", "all"], default="all")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", default="results/latest")
    parser.add_argument("--ocr-timeout", type=float, default=180)
    parser.add_argument("--real-pdf", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.repeats <= 10:
        parser.error("repeats must be 1..10")
    asyncio.run(benchmark(args))


if __name__ == "__main__":
    main()
