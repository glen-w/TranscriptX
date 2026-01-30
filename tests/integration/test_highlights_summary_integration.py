from pathlib import Path

from transcriptx.core.analysis.highlights import (  # type: ignore[import-untyped]
    HighlightsAnalysis,
)
from transcriptx.core.analysis.summary import (  # type: ignore[import-untyped]
    SummaryAnalysis,
)
from transcriptx.core.pipeline.pipeline_context import (  # type: ignore[import-untyped]
    PipelineContext,
)


def test_highlights_summary_outputs(tmp_path) -> None:
    transcript_path = (
        Path(__file__).resolve().parent.parent
        / "fixtures"
        / "data"
        / "tiny_diarized.json"
    )
    context = PipelineContext(
        transcript_path=str(transcript_path),
        output_dir=str(tmp_path),
        use_db=False,
    )
    highlights_result = HighlightsAnalysis().run_from_context(context)
    assert highlights_result["status"] == "success"

    summary_result = SummaryAnalysis().run_from_context(context)
    assert summary_result["status"] == "success"

    output_dir = Path(context.get_transcript_dir())
    highlights_json = list(output_dir.glob("highlights/data/global/*_highlights.json"))
    highlights_md = list(output_dir.glob("highlights/data/global/*_highlights.md"))
    summary_json = list(output_dir.glob("summary/data/global/*_summary.json"))
    summary_md = list(output_dir.glob("summary/data/global/*_summary.md"))

    assert highlights_json, "Expected highlights JSON artifact"
    assert highlights_md, "Expected highlights Markdown artifact"
    assert summary_json, "Expected summary JSON artifact"
    assert summary_md, "Expected summary Markdown artifact"
