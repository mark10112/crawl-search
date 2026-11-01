# Round 3c: source-format-aware guard and conservative detail routing

Retain the full paired round-3 trial and round-3b after trial, including regressions. Compare a frozen final candidate against the exact eight fresh 633aa9d baseline reads from round 3 in the same turn. Baseline raw files copied byte-identically with hashes/timestamps; not another fully paired A/B or statistical result. Same four PDFs, three pages, modes/order/cache=false/max_chars=40000, 24 sampled spans and 15 strict rows, model/revision/8192, MLX reset and identical English warmup.

Diagnosis: an actual Census table image has printed dot leaders. The old guard cancelled at The State plus 48 printed periods, before its values were fully read. Semantic letters/numbers/marks retain the original 20x repetition guard; decorative punctuation is allowed up to a separate 1024-character runaway bound. Numeric zero / Greek-letter loops remain rejected. This is classification of source formatting, not deleting or correcting table values.

Detail policy: small pages use up to 300 DPI. For pages that would exceed 4MP, a bounded <=500k-pixel preview checks for four separated long vertical rules. Ruled/dense table pages keep high detail within 12MP/20MiB; large plain pages retain the 144-DPI baseline, avoiding the observed Royal CER regression. Every actual selected DPI is recorded.

Dense tables retain source-contiguous banding. If all bands finish but structure disagrees, those results are not accepted or padded; perform one new recognition of the full original high-detail table crop and retain both attempts. The previously validated one-page baseline retry remains only after a failed detail page. No source-specific route, reference lookup, numeric repair, CPU prototype output or relaxed semantic repetition check.

Count all failed attempts in timing/resources. Verify final selected page completions, CER and strict rows separately from attempts. No external document upload/Firecrawl, no main merge. Always restore production. This development corpus has been used for diagnosis; results are not holdout generalization.
