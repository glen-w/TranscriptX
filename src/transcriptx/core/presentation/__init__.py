"""
Presentation helpers for human-facing outputs.
"""

from .anchors import format_segment_anchor, format_segment_anchor_md, format_timecode
from .intensity import bucket, render_intensity_line
from .nothing_found import render_no_signal_md
from .provenance import build_md_provenance, render_provenance_footer_md

__all__ = [
    "format_timecode",
    "format_segment_anchor",
    "format_segment_anchor_md",
    "bucket",
    "render_intensity_line",
    "render_no_signal_md",
    "build_md_provenance",
    "render_provenance_footer_md",
]
