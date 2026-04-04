"""Group-level aggregate chart generation (post aggregation row writes).

Operator note: default group overview strip vs gallery is documented in
``docs/groups/group_charts_default_overview.md`` (not this package's internals).
"""

from transcriptx.core.analysis.group_charts.context import GroupChartContext
from transcriptx.core.analysis.group_charts.result import GroupChartRunResult
from transcriptx.core.analysis.group_charts.runner import run_group_aggregate_charts
from transcriptx.core.analysis.group_charts.virtual_path import (
    build_group_virtual_transcript_path,
)

__all__ = [
    "GroupChartContext",
    "GroupChartRunResult",
    "build_group_virtual_transcript_path",
    "run_group_aggregate_charts",
]
