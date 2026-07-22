"""Register built-in view blocks."""

from __future__ import annotations

from transcriptx.web.blocks.implementations import asr_confidence as asr_confidence_blocks
from transcriptx.web.blocks.implementations import charts as charts_blocks
from transcriptx.web.blocks.implementations import data as data_blocks
from transcriptx.web.blocks.implementations import insights as insights_blocks
from transcriptx.web.blocks.implementations import overview as overview_blocks
from transcriptx.web.blocks.implementations import overview_curated as curated_blocks
from transcriptx.web.blocks.registry import register_block
from transcriptx.web.blocks.specs import BlockPrereq, BlockSpec

_BUILTIN_REGISTERED = False


def register_builtin_blocks() -> None:
    global _BUILTIN_REGISTERED
    if _BUILTIN_REGISTERED:
        return
    _register_overview_blocks()
    _register_curated_overview_blocks()
    _register_insights_blocks()
    _register_charts_data_blocks()
    _BUILTIN_REGISTERED = True


def _register_curated_overview_blocks() -> None:
    specs = [
        BlockSpec(
            id="transcript_summary_hero",
            title="Transcript summary",
            group="Overview",
            description="Primary transcript summary with LLM → narrative → executive precedence.",
            prerequisites=BlockPrereq.RUN_SCOPED,
            render=curated_blocks.render_transcript_summary_hero,
        ),
        BlockSpec(
            id="other_summaries",
            title="Other summaries",
            group="Insights",
            description="Secondary summary alternatives under the primary hero.",
            prerequisites=BlockPrereq.RUN_SCOPED,
            render=curated_blocks.render_other_summaries,
        ),
        BlockSpec(
            id="at_a_glance",
            title="At a glance",
            group="Overview",
            description="Compact duration, speakers, modules, and artifact counts.",
            prerequisites=BlockPrereq.RUN_SCOPED,
            render=curated_blocks.render_at_a_glance,
        ),
        BlockSpec(
            id="speaker_summary_cards",
            title="Speakers",
            group="Overview",
            description="Per-speaker talk time, WPM, segments, and a fourth highlight stat.",
            artifact_patterns=("report.json", "stats/speaker_rows.json"),
            prerequisites=BlockPrereq.RUN_SCOPED,
            render=curated_blocks.render_speaker_summary_cards,
        ),
        BlockSpec(
            id="action_items_compact",
            title="Action items",
            group="Overview",
            description="Compact LLM action items list.",
            module_deps=("llm_action_items",),
            artifact_patterns=(
                "_llm_action_items.json",
                "_llm_action_items.md",
                "action_item_rows.json",
            ),
            prerequisites=BlockPrereq.RUN_SCOPED,
            render=curated_blocks.render_action_items_compact,
        ),
        BlockSpec(
            id="highlights_compact",
            title="Highlights",
            group="Overview",
            description="Compact top highlights and themes.",
            module_deps=("highlights",),
            artifact_patterns=("_highlights.json", "highlight_rows.json"),
            prerequisites=BlockPrereq.RUN_SCOPED,
            render=curated_blocks.render_highlights_compact,
        ),
        BlockSpec(
            id="run_status_compact",
            title="Run status",
            group="Overview",
            description="Quiet run status with separate artifact health and execution details.",
            prerequisites=BlockPrereq.RUN_SCOPED,
            render=curated_blocks.render_run_status_compact,
        ),
    ]
    for spec in specs:
        register_block(spec)


def _register_overview_blocks() -> None:
    specs = [
        BlockSpec(
            id="run_health",
            title="Run health",
            group="Overview",
            description="Artifact health status, errors, and warnings.",
            prerequisites=BlockPrereq.RUN_SCOPED,
            render=overview_blocks.render_run_health,
        ),
        BlockSpec(
            id="run_outcomes",
            title="Run outcomes",
            group="Overview",
            description="Included, excluded, failed, and skipped modules.",
            prerequisites=BlockPrereq.RUN_SCOPED,
            render=overview_blocks.render_run_outcomes,
        ),
        BlockSpec(
            id="artifact_metrics",
            title="Artifact metrics",
            group="Overview",
            description="Counts and disk size for run artifacts.",
            prerequisites=BlockPrereq.RUN_SCOPED,
            render=overview_blocks.render_artifact_metrics,
        ),
        BlockSpec(
            id="module_navigator",
            title="Analysis modules",
            group="Overview",
            description="Select and browse analysis module outputs.",
            prerequisites=BlockPrereq.RUN_SCOPED,
            render=overview_blocks.render_module_navigator,
        ),
        BlockSpec(
            id="module_metrics",
            title="Module metrics",
            group="Overview",
            description="Key metrics and highlights for the selected analysis module.",
            prerequisites=BlockPrereq.RUN_SCOPED,
            artifact_kinds=("data_json",),
            render=overview_blocks.render_module_metrics,
        ),
        BlockSpec(
            id="module_summary_table",
            title="Per-module summary",
            group="Overview",
            description="Charts and data file counts per module.",
            prerequisites=BlockPrereq.RUN_SCOPED,
            render=overview_blocks.render_module_summary_table,
        ),
        BlockSpec(
            id="export_panel",
            title="Export",
            group="Overview",
            description="Zip export for selected artifacts.",
            prerequisites=BlockPrereq.RUN_SCOPED,
            render=overview_blocks.render_export_panel,
        ),
    ]
    for spec in specs:
        register_block(spec)


def _register_insights_blocks() -> None:
    llm_params_schema = {
        "type": "object",
        "properties": {
            "module": {"type": "string"},
            "title": {"type": "string"},
            "artifact_stem": {"type": "string"},
            "text_field": {"type": "string"},
            "empty_hint": {"type": "string"},
            "instance_id": {"type": "string"},
        },
    }
    specs = [
        BlockSpec(
            id="asr_confidence",
            title="ASR Confidence",
            group="Insights",
            description=(
                "Word-score coverage, low-confidence spans/clusters, and "
                "open-in-transcript review. Model uncertainty evidence — not WER."
            ),
            module_deps=("transcript_quality",),
            artifact_patterns=("_transcript_quality.json",),
            prerequisites=BlockPrereq.RUN_SCOPED,
            render=asr_confidence_blocks.render_asr_confidence,
        ),
        BlockSpec(
            id="insights_contract",
            title="Content vs Style",
            group="Insights",
            description="Key themes, recurring ideas, and style markers.",
            module_deps=("insights",),
            artifact_patterns=("_insights.json", "insight_rows.json"),
            prerequisites=BlockPrereq.RUN_SCOPED,
            render=insights_blocks.render_insights_contract,
        ),
        BlockSpec(
            id="highlights",
            title="Highlights",
            group="Insights",
            description="Themes, tension points, and filtered highlight quotes.",
            module_deps=("highlights",),
            artifact_patterns=("_highlights.json", "highlight_rows.json"),
            prerequisites=BlockPrereq.RUN_SCOPED,
            render=insights_blocks.render_highlights,
        ),
        BlockSpec(
            id="executive_summary",
            title="Executive Summary",
            group="Insights",
            description="Summary module prose or JSON.",
            module_deps=("summary",),
            artifact_patterns=("_summary.json", "_summary.md", "summary.json"),
            prerequisites=BlockPrereq.RUN_SCOPED,
            render=insights_blocks.render_executive_summary,
        ),
        BlockSpec(
            id="commitments_table",
            title="Commitments",
            group="Insights",
            description="Commitments and next steps from summary module.",
            module_deps=("summary",),
            artifact_patterns=("_summary.json", "summary.json"),
            prerequisites=BlockPrereq.RUN_SCOPED,
            render=insights_blocks.render_commitments_table,
        ),
        BlockSpec(
            id="llm_summary_block",
            title="LLM Summary",
            group="Insights",
            description="LLM-generated transcript or narrative summary.",
            module_deps=("llm_summary", "narrative_summary"),
            artifact_patterns=(
                "_llm_summary.json",
                "_llm_summary.md",
                "_narrative_summary.json",
                "_narrative_summary.md",
                "llm_summary.json",
                "group_llm_summary.json",
            ),
            prerequisites=BlockPrereq.RUN_SCOPED,
            params_schema=llm_params_schema,
            render=insights_blocks.render_llm_summary_block,
        ),
        BlockSpec(
            id="llm_speaker_summary_block",
            title="Per-Speaker LLM Summaries",
            group="Insights",
            description="LLM-generated summary for each named speaker.",
            module_deps=("llm_speaker_summary",),
            artifact_patterns=(
                "_llm_speaker_summary_index.json",
                "group_llm_speaker_summary_index.json",
            ),
            prerequisites=BlockPrereq.RUN_SCOPED,
            render=insights_blocks.render_llm_speaker_summary_block,
        ),
        BlockSpec(
            id="llm_action_items_block",
            title="Action Items",
            group="Insights",
            description="Structured action items extracted via local LLM.",
            module_deps=("llm_action_items",),
            artifact_patterns=(
                "_llm_action_items.json",
                "_llm_action_items.md",
                "action_item_rows.json",
            ),
            prerequisites=BlockPrereq.RUN_SCOPED,
            render=insights_blocks.render_llm_action_items_block,
        ),
        BlockSpec(
            id="lexical_diversity_block",
            title="Lexical Diversity",
            group="Insights",
            description="TTR, MTLD, and hapax rate metrics by speaker.",
            module_deps=("lexical_diversity",),
            artifact_patterns=(
                "_lexical_diversity.json",
                "_lexical_diversity.csv",
                "session_rows.json",
                "speaker_rows.json",
            ),
            prerequisites=BlockPrereq.RUN_SCOPED,
            render=insights_blocks.render_lexical_diversity_block,
        ),
    ]
    for spec in specs:
        register_block(spec)


def _register_charts_data_blocks() -> None:
    specs = [
        BlockSpec(
            id="chart_overview_slots",
            title="Chart overview slots",
            group="Charts",
            description="Configured overview chart slots from run config.",
            prerequisites=BlockPrereq.RUN_SCOPED,
            artifact_kinds=("chart_static", "chart_dynamic"),
            render=charts_blocks.render_chart_overview_slots,
        ),
        BlockSpec(
            id="chart_gallery",
            title="Chart gallery",
            group="Charts",
            description="Per-module chart gallery sections.",
            prerequisites=BlockPrereq.RUN_SCOPED,
            artifact_kinds=("chart_static", "chart_dynamic"),
            render=charts_blocks.render_chart_gallery,
        ),
        BlockSpec(
            id="data_artifact_preview",
            title="Data artifact preview",
            group="Data",
            description="Preview selected data artifact contents.",
            prerequisites=BlockPrereq.RUN_SCOPED,
            artifact_kinds=("data_json", "data_csv", "data_txt"),
            render=data_blocks.render_data_artifact_preview,
        ),
    ]
    for spec in specs:
        register_block(spec)
