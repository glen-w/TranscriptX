"""
Analysis results integration for advanced semantic similarity.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import log_info, log_warning


def load_analysis_results(transcript_path: str, log_tag: str) -> dict[str, Any]:
    """Load existing analysis results for integration."""
    try:
        config = get_config()
        output_dir = Path(config.output.base_output_dir)
        transcript_name = Path(transcript_path).stem

        analysis_results: dict[str, Any] = {}
        analysis_modules = [
            "sentiment",
            "emotion",
            "acts",
            "tics",
            "understandability",
        ]

        for module in analysis_modules:
            module_dir = output_dir / transcript_name / module
            if not module_dir.exists():
                continue
            try:
                summary_file = module_dir / f"{module}_summary.json"
                if summary_file.exists():
                    with open(summary_file) as handle:
                        analysis_results[module] = json.load(handle)
                else:
                    global_file = module_dir / "global" / f"{module}_global.json"
                    if global_file.exists():
                        with open(global_file) as handle:
                            analysis_results[module] = json.load(handle)
            except Exception as exc:
                log_warning(log_tag, f"Failed to load {module} results: {exc}")

        log_info(log_tag, f"Loaded {len(analysis_results)} analysis modules")
        return analysis_results
    except Exception as exc:
        log_warning(log_tag, f"Failed to load analysis results: {exc}")
        return {}
