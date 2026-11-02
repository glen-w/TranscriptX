# Maintainability layout (2026-11-02)

Behaviour-preserving file splits from the 2026-11-02 `/refactor` assessment.
Do **not** merge `core.utils.config` with `core.config`, rewrite Streamlit, unify
“profile” types, or epic-migrate `processing_state`.

| Surface | Facade / catalog | Implementation home |
|---------|------------------|---------------------|
| Group aggregation | `core/analysis/aggregation/registry.py` | `aggregators.py` (+ domain modules such as `emotion.py`, `topics.py`) |
| Insights blocks | `web/blocks/implementations/insights.py` | `insights_support.py`, `insights_contract.py`, `insights_highlights.py`, `insights_llm.py`, `insights_markers.py` |
| Analysis config dataclasses | `core/utils/config/analysis.py` | `analysis_*.py` 1:1 with `core/config/models/` pilots; hydrate in `analysis_hydrate.py` |
| Speakers directory UI | `web/page_modules/speakers.py` | `web/ui/speakers/` (`support`, `directory`, `detail`, `charts`, `forms`) |
| Speaker ID page | `web/page_modules/speaker_id.py` | `web/workspaces/speaker_id_session_keys.py`, `speaker_id_voice.py` |
| Transcript path cache | re-export from `web/cache_helpers.py` | `web/transcript_path_cache.py` (FileService must not import `cache_helpers`) |
| STT `SPEAKER_XX` labels | converter wrappers | `services/transcription/speaker_label.py` (`one_based=True` Granite, `False` Nemotron) |
| Lexical emotion | `EmotionAnalysis.analyze` envelope | `_analyze_lexical` scoring; `_save_results` unchanged |

Gates and anti-patterns: [COMPLEXITY_GATES.md](COMPLEXITY_GATES.md), [web_blocks.md](web_blocks.md), [config_architecture.md](config_architecture.md).
