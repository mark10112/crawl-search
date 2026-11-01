"""Persistent, killable OCR subprocess. stdout is JSON-lines only."""
import contextlib
import json
import os
import sys
import time
from pathlib import Path


def fast_ocr(path):
    import pymupdf
    tessdata = Path(os.getenv("LOCAL_RESEARCH_TESSDATA", ".cache/tessdata")).resolve()
    if not all((tessdata / f"{lang}.traineddata").exists() for lang in ["eng", "tha"]):
        raise RuntimeError("Thai/English Tesseract language files missing; run setup.ps1")
    with pymupdf.open(path) as document:
        text = []
        for index, page in enumerate(document):
            tp = page.get_textpage_ocr(language="eng+tha", dpi=150, full=True, tessdata=str(tessdata))
            text.append(f"<!-- subset page {index + 1} -->\n" + page.get_text(textpage=tp))
        return "\n\n".join(text)


def main():
    converter = None
    fast_started = False
    for line in sys.stdin:
        start = time.perf_counter()
        engine = None
        try:
            request = json.loads(line)
            requested = request.get("engine", "auto")
            fast_error = None
            with contextlib.redirect_stdout(sys.stderr):
                if requested in {"auto", "tesseract"}:
                    cold = not fast_started
                    try:
                        text = fast_ocr(request["path"])
                        fast_started = True
                        if len(text.strip()) < 100:
                            raise RuntimeError("Fast OCR returned too little text")
                        engine = "pymupdf-tesseract"
                    except Exception as exc:
                        if requested == "tesseract":
                            raise
                        fast_error = str(exc)
                if engine is None and converter is None:
                    from docling.datamodel.base_models import InputFormat
                    from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions
                    from docling.datamodel.accelerator_options import AcceleratorOptions, AcceleratorDevice
                    from docling.document_converter import DocumentConverter, PdfFormatOption
                    options = PdfPipelineOptions()
                    options.do_ocr = True
                    options.do_table_structure = False
                    options.ocr_options = EasyOcrOptions(lang=["th", "en"], force_full_page_ocr=True)
                    options.accelerator_options = AcceleratorOptions(num_threads=4, device=AcceleratorDevice.CPU)
                    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
                    cold = True
                elif engine is None:
                    cold = False
                if engine is None:
                    result = converter.convert(request["path"])
                    text = result.document.export_to_markdown()
                    if hasattr(result.input, "release"):
                        result.input.release()
                    engine = "docling-easyocr"
            payload = {"ok": True, "text": text, "cold": cold,
                       "engine": engine, "fast_ocr_error": fast_error,
                       "conversion_ms": round((time.perf_counter() - start) * 1000, 2)}
        except Exception as exc:
            payload = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        print(json.dumps(payload, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
