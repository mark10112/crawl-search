# Crawl Search

- Main package: `research-tools/local-research`; this is a standalone repository, not the novel project.
- Mac target is Apple M4 arm64 with 16 GiB unified memory. Treat CUDA service code as the measured baseline, not a working Mac backend.
- Keep secrets, host-specific SSH configuration/keys, environments, runtime cache, model weights and original document downloads outside Git.
- Run appropriate routing tests after changes. Browser tests require the browser extra.
- Preserve original benchmark observations and clearly separate baseline, fixes, and supplemental experiments. Never drop failed or incomplete outputs to improve scores.
- An OCR success requires explicit completeness checks; long text alone is insufficient. Preserve page/region provenance and table structure.
- Store versioned dependencies, model revisions and prompts with benchmark results. Distinguish verified runtime results from proposed Apple Silicon compatibility.
