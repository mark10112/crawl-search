# OCR models to benchmark next — checked 1 November 2026

Detected hardware: NVIDIA GeForce RTX 4060, 8188 MiB VRAM (nvidia-smi), 16 GiB system RAM. GPU access from a Docker container has not yet been verified. Model weights, inference memory, context/KV cache, layout models and Docker image size are different measurements.

| Candidate | Why it is relevant | Thai evidence | Deployment / limitations |
|---|---|---|---|
| **PP-OCRv5 mobile Thai through RapidOCR + ONNX Runtime** | Small OCR detector/recognizer rather than a generative billion-parameter model; first CPU candidate | Explicit `th_PP-OCRv5_rec_mobile`, Thai/English in official model table | Self-hosted CPU Docker is practical. Must benchmark recognition, reading order and scans; not a complete layout/table parser by itself. |
| **Typhoon OCR 1.5 2B** | Purpose-built Thai/English document parser; first GPU quality candidate | Official model card tags Thai and English and documents the required OCR prompt | Local vLLM / Transformers. Official hardware guide says 8–12 GB VRAM, so this 8 GB card is at the lower edge: limit context and concurrency and verify peak VRAM. Do not assume a benchmark on L4/H100 transfers to RTX 4060. |
| **Typhoon OCR 1.5 3B QAT, Q4_K_M via official SCB10X Ollama listing** | A separate model with an official quantized distribution; convenient local runner | Official listing describes bilingual Thai/English | Ollama artifact is 3.2 GB; this is disk/download size, NOT total VRAM. This is not simply the 2B checkpoint renamed. Requires the model-specific OCR prompt. |
| **PaddleOCR-VL 1.6, nominal 0.9B family** | Compact document VLM for text/table/formula/layout; official Docker path | Multilingual document family; Thai-specific accuracy on our scans still needs testing | Official GPU Docker image exists, but online image is about 8 GB on disk. Small parameter count does not imply a tiny container. Architecture is compatible with 1.5. |
| **LightOnOCR-2-1B** | Small end-to-end OCR VLM; useful comparison for English | Official listed languages do not include Thai | Lower priority for Thai research. Model card also points to a newer 4B model, which is a different size class. |

Do not select PP-OCRv6 tiny just because it is newer: the installed RapidOCR 3.10.0 model-route language sets for v6 tiny/small omit `th`, while v5 has an explicit Thai route. Recheck the route table if upgrading.

## Current package baseline

The implemented default is PDF text -> local Tesseract Thai/English -> optional Docling/EasyOCR if the first OCR stage fails, with manual engine override. Tesseract completed the controlled one-page sample in roughly 0.33 seconds warm; initial Docling/EasyOCR took roughly 21 seconds warm and omitted some known lines. This is a single synthetic fixture, not evidence that Tesseract beats modern VLMs on historical scans. The initial prototype's permissive English-only success gate was tightened to require all English and Thai anchors; its earlier success labels must not be used as a completeness score.

No Typhoon, PaddleOCR-VL or LightOn model has been downloaded or performance-tested in this package yet. The recommendations above are based on primary documentation, not invented local measurements.

## Sources

- [RapidOCR official model table](https://rapidai.github.io/RapidOCRDocs/latest/model_list/) and [model routing configuration](https://github.com/RapidAI/RapidOCR/blob/main/python/rapidocr/default_models.yaml)
- [Typhoon OCR 1.5 2B model card — current canonical organization](https://huggingface.co/typhoon-ai/typhoon-ocr1.5-2b)
- [Typhoon hardware guide](https://docs.opentyphoon.ai/en/deploy-hardware/), page last updated 14 November 2025
- [Official SCB10X Ollama 3B QAT listing](https://ollama.com/scb10x/typhoon-ocr1.5-3b)
- [PaddleOCR-VL 1.6 model card](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6) and [official Docker/deployment instructions](https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PaddleOCR-VL.html)
- [LightOnOCR-2-1B language metadata and model card](https://huggingface.co/lightonai/LightOnOCR-2-1B/raw/main/README.md)
- [PyMuPDF integrated Tesseract OCR installation notes](https://pymupdf.readthedocs.io/en/latest/installation.html)
