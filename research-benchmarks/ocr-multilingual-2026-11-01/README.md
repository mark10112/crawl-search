# Docker multilingual OCR benchmark

See METHOD.md for the predeclared dataset, scoring and hardware limits. Model cards used to configure inference are saved beside the scripts.

```powershell
docker build -t ocr-multilingual-bench:2026-11-01 .
.\run.ps1 -Model all -Repeats 3
# Use an available Python with standard library only for aggregation:
python summarize.py
```

The dataset is already supplied in `dataset/`; generating it again requires Playwright + Chromium and Pillow on Windows with the system fonts used by make_dataset.py. No source text is sent to the OCR models, only the image. The model cache is Docker volume `ocr-benchmark-models`, shared across sequential runs. No paid API is called. Do not launch the model runs concurrently if comparing their memory and latency.

Each VLM revision is pinned in model-revisions.json when resolved. The run's exact installed package versions are copied into each results JSON. A model name alone is not a reproducible checkpoint version.

The main accuracy summary equally weights the eight clean monolingual documents. Mixed-language and degraded pages are also reported separately. Three timing repetitions of the same page are not three independent accuracy samples. CER is lower-is-better and can exceed 100% for invented/repeated output; it is not an LLM judge score.

Results from incomplete setup checks are retained under `*-setup-check.*` and excluded from final aggregation. The Arabic dependency was added before the final RapidOCR run. The Paddle model-card example used an image-processor attribute absent from the installed Transformers API; the final run uses the checkpoint processor defaults instead. No page-specific prompt/recognizer tuning is applied based on scored outputs.

LightOn uses its named model/processor classes rather than AutoModel's Mistral3 mapping; final loading was audited with no missing/unexpected/mismatched weights. The same loading audit was also run for Paddle separately from timing. A JSON metadata serialization setup check is preserved separately. `verify_results.py` independently recomputes Levenshtein distances and checks all 117 scored rows plus image hashes.

Raw outputs, timings, CUDA peaks, startup records, errors and RSS/VRAM samples are in results/{rapid,paddle,lighton}.json. Desktop/background VRAM is included in device-wide samples; Torch allocated peak is a separate field. All comparisons are local Docker runs on the same machine.
