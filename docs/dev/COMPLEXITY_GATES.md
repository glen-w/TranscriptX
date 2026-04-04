Type: PRODUCT
Authority: self

# Complexity and performance gates (pipeline / reporting)

- **Radon (optional):** `radon cc src/transcriptx/core/pipeline -a -nc` — watch for new `F` ranks in hot paths touched by changes.
- **Cold/warm import baseline:** `python scripts/bench_pipeline_cold_warm.py` — record numbers when changing pipeline imports or startup.

These are lightweight regression signals; CI can run them as non-blocking or nightly jobs.
