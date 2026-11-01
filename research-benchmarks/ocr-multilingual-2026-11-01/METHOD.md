# Multilingual OCR benchmark — 1 November 2026

Three separate Docker runs on the user's machine, one model at a time. GPU: RTX 4060 8188 MiB; system RAM 16 GiB; Docker VM about 7.67 GiB and 12 logical CPUs. Desktop/background GPU use is recorded separately.

Models fixed before scoring: RapidOCR 3.10.0 with PP-OCRv5 mobile detector and script-specific mobile recognizers (CPU ONNX, four threads); PaddleOCR-VL-1.6 and LightOnOCR-2-1B (CUDA BF16, SDPA, batch one, no quantization). HF checkpoint revisions are resolved and recorded. RapidOCR receives the known script; this excludes language detection and benefits its result. This is a deployment comparison, not identical hardware compute: CPU Rapid versus GPU VLMs.

All models receive identical image bytes: eight self-authored single-language documents (English, French, German, Thai, Chinese, Japanese, Arabic, Hindi), two mixed-language documents, and three lower-resolution/contrast versions. Original reference text is authored before OCR. Image SHA256s and references are in dataset/manifest.json. Fonts/shaping are rendered in a browser and contact-sheet checked. These controlled pages do not represent the user's entire historical-source collection.

The primary quality figure is mean CER across the eight clean monolingual pages, with equal weight per language. Mixed/degraded results and the 13-page mean are separate. Each page is repeated three times with deterministic generation; repetitions improve timing observations, not the number of independent quality samples. CER uses Levenshtein edits after Unicode NFC, whitespace removal and Markdown/HTML presentation removal, preserving case, punctuation and diacritics. CER may exceed 100% for hallucinated/repeated output. Errors/empty output count as CER 100%, not excluded as successful reads.

Each model is loaded, followed by one excluded first-inference warmup, then warm runs. Download/load time and first inference are reported separately. Latency includes input preprocessing, generation/recognition and decode; CUDA is synchronized. VLMs use at most 768 new tokens and a 45-second generation limit; truncations are reported. No page-specific tuning based on test results.

Process-tree RSS and device-wide VRAM are sampled at 100 ms. Torch allocation/reservation peaks are also recorded per page. Device-wide VRAM includes desktop/background usage and is not all model memory. RSS excludes reclaimable filesystem cache and may double-count shared process pages. Load/first-inference resource peaks are separated from warm-run peaks.

Paddle's official model card warns that direct Transformers checkpoint inference is element recognition/text spotting, not the complete official page-layout pipeline. This test uses single-block documents and the documented OCR prompt, with no external layout detector or oracle crops. It does not rank Paddle's complete document-parsing service against the other pipelines. LightOn's documented language list omits Thai/Arabic/Hindi; these remain in the test because the user's corpus is heterogeneous, and per-language scores must accompany averages.

No novel files are modified, no paid inference APIs are used, and no cloud GPU is used.
