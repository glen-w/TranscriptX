"""Present pipeline run progress to reporters and UIs."""

from __future__ import annotations

from typing import Any, Dict, List

from transcriptx.core.pipeline.output_reporter import (
    display_output_summary_to_user,
    generate_comprehensive_output_summary,
    print_compact_post_run_summary,
    print_review_before_run,
)


class PipelineRunPresenter:
    def show_pre_run_review(self, review: Dict[str, Any]) -> None:
        print_review_before_run(review)

    def build_summary(
        self,
        *,
        transcript_path: str,
        selected_modules: List[str],
        modules_run: List[str],
        errors: List[str],
        skipped_modules: List[Any],
    ) -> Dict[str, Any]:
        return generate_comprehensive_output_summary(
            transcript_path=transcript_path,
            selected_modules=selected_modules,
            modules_run=modules_run,
            errors=errors,
            skipped_modules=skipped_modules,
        )

    def show_post_run_summary(
        self, summary: Dict[str, Any], output_dir: str, results: Dict[str, Any]
    ) -> None:
        display_output_summary_to_user(summary)
        print_compact_post_run_summary(output_dir, results)
