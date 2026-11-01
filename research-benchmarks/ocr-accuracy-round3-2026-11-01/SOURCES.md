# Research sources and status

Official PP-OCRv5 Thai model/API: https://huggingface.co/PaddlePaddle/th_PP-OCRv5_mobile_rec and https://www.paddleocr.ai/latest/en/version3.x/module_usage/text_recognition.html . Small finite CPU recognizers were investigated, but are not enabled in the measured candidate; see pilot artifacts and experimental_accuracy.py. No reference values are supplied to these probes.

Local source-image audit: source PDF embedded raster dimensions were inspected with PyMuPDF get_images(); Gazette ~1283x2006 in a ~308x481 point page, Census ~2589x3331 in a ~610x791 point page, Preservation ~2684x4368 in a ~381x629 point page. The old 144-DPI renderer discards real input detail. Candidate rendering uses at most 300 DPI, reduced only for 12MP/20MiB safety bounds.

Primary benchmark protocol is METHOD.md. Pilots are development observations, never a replacement for the complete paired corpus comparison.
