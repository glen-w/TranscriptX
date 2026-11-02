# Complexity and performance gates (pipeline / reporting)

- **Radon (optional):** `radon cc src/transcriptx/core/pipeline -a -nc` — watch for new `F` ranks in hot paths touched by changes.
- **Cold/warm import baseline:** `python scripts/bench_pipeline_cold_warm.py` — record numbers when changing pipeline imports or startup.
- **Group aggregation:** keep `aggregation/registry.py` as the catalog (`AggregationEntry` + `build_registry`). New row/blob aggregators go in `aggregation/aggregators.py` (or a domain module like `aggregation/topics.py`), not inline in the registry.
- **Insights blocks:** keep `web/blocks/implementations/insights.py` as the re-export facade. New contract / highlights / LLM / marker renderers go in `insights_contract.py`, `insights_highlights.py`, `insights_llm.py`, or `insights_markers.py` (shared loaders in `insights_support.py`). Tests that patch Streamlit must use `tests/web/insights_block_patches.py` so every slice module sees the dummy.

These are lightweight regression signals; CI can run them as non-blocking or nightly jobs.
