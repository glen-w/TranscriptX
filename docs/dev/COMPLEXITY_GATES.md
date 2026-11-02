# Complexity and performance gates (pipeline / reporting)

- **Radon (optional):** `radon cc src/transcriptx/core/pipeline -a -nc` — watch for new `F` ranks in hot paths touched by changes.
- **Cold/warm import baseline:** `python scripts/bench_pipeline_cold_warm.py` — record numbers when changing pipeline imports or startup.
- **Group aggregation:** keep `aggregation/registry.py` as the catalog (`AggregationEntry` + `build_registry`). New row/blob aggregators go in `aggregation/aggregators.py` (or a domain module like `aggregation/topics.py`), not inline in the registry.
- **Insights blocks:** keep `web/blocks/implementations/insights.py` as the re-export facade. New contract / highlights / LLM / marker renderers go in `insights_contract.py`, `insights_highlights.py`, `insights_llm.py`, or `insights_markers.py` (shared loaders in `insights_support.py`). Tests that patch Streamlit must use `tests/web/insights_block_patches.py` so every slice module sees the dummy.
- **Analysis config facade:** keep `utils/config/analysis.py` as the re-export plus `AnalysisConfig`. Nested dataclasses go in `analysis_*.py` matching `core/config/models/` pilots; shared hydrate helpers stay in `analysis_hydrate.py`. Do not add module-level Pydantic model imports.
- **Speakers directory UI:** keep `web/page_modules/speakers.py` as the import facade. Render helpers live under `web/ui/speakers/` (`support`, `directory`, `detail`, `charts`, `forms`). Leave `SpeakerProfileService` in `core.speaker_profiles`. Tests that patch Streamlit must use `tests/web/speakers_page_patches.py`.
- **Speaker ID page:** keep `web/page_modules/speaker_id.py` as the page/CCv2 host. Transcript-scoped session keys live in `web/workspaces/speaker_id_session_keys.py`; voice callbacks/UI live in `web/workspaces/speaker_id_voice.py`. Do not change `app/speaker_id` protocol/service behaviour.

These are lightweight regression signals; CI can run them as non-blocking or nightly jobs.
