"""Build a single PDF of all run charts with subheadings per module."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from transcriptx.core.utils.logger import get_logger

logger = get_logger()

# Reportlab is lazy-loaded via get_reportlab() when building the PDF

# Raster image extensions we can embed (ReportLab doesn't render SVG directly)
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}

# Module names to sort to the end (summary, assets, debug, etc.)
_TAIL_MODULES = frozenset({"summary", "assets", "debug", "other"})


def _natural_sort_key(path: Path) -> Tuple[Any, ...]:
    """Sort key that orders filenames naturally (e.g. chart_2 before chart_10)."""
    s = path.name
    return tuple(
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", s)
    )


def _pixels_to_points(
    width_px: int, height_px: int, dpi: Tuple[float, float] | float | None
) -> Tuple[float, float]:
    """Convert pixel dimensions to PDF points (1/72 inch). No upscaling.

    If DPI is missing, assumes 96 (common screen). Result is capped so that
    the image never exceeds the logical size implied by DPI (we don't upscale).
    """
    if dpi is None:
        dpi_x = dpi_y = 96.0
    elif isinstance(dpi, (int, float)):
        dpi_x = dpi_y = float(dpi)
    else:
        dpi_x, dpi_y = float(dpi[0]), float(dpi[1])
    if dpi_x <= 0:
        dpi_x = 96.0
    if dpi_y <= 0:
        dpi_y = 96.0
    width_pt = width_px * 72.0 / dpi_x
    height_pt = height_px * 72.0 / dpi_y
    return (width_pt, height_pt)


def collect_charts_by_module(run_root: Path) -> Dict[str, List[Path]]:
    """Collect all chart image paths under run_root, grouped by module name.

    Module name is the directory immediately above the first "charts" in the path
    (e.g. emotion/charts/... -> emotion; by_session/session_01/emotion/charts/... -> emotion).
    Only walks inside directories named "charts" for performance.
    """
    run_root = Path(run_root).resolve()
    by_module: Dict[str, List[Path]] = {}

    for charts_dir in run_root.rglob("charts"):
        if not charts_dir.is_dir():
            continue
        for path in charts_dir.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in _IMAGE_SUFFIXES:
                continue
            try:
                rel = path.relative_to(run_root)
            except ValueError:
                continue
            parts = rel.parts
            if "charts" not in parts:
                continue
            idx = parts.index("charts")
            module = parts[idx - 1] if idx > 0 else "other"
            if module not in by_module:
                by_module[module] = []
            by_module[module].append(path)

    for key in by_module:
        by_module[key].sort(key=_natural_sort_key)

    return by_module


def _get_reportlab_flowables():
    """Lazy-load reportlab and return (SimpleDocTemplate, A4, styles, ParagraphStyle, ...)."""
    from transcriptx.core.utils.lazy_imports import get_reportlab

    get_reportlab()  # ensure reportlab is installed/loaded
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import (
        Image as RLImage,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
    )

    return (
        SimpleDocTemplate,
        A4,
        getSampleStyleSheet,
        ParagraphStyle,
        inch,
        TA_CENTER,
        RLImage,
        PageBreak,
        Paragraph,
        Spacer,
    )


def build_charts_pdf(run_root: Path, output_pdf_path: Path) -> Path | None:
    """Build a PDF containing all charts with a subheading per module.

    Includes a cover page (run name, timestamp, chart count), module sections
    with Heading2, captions under each chart, and page breaks between modules.
    Requires reportlab (lazy-loaded; may be installed on first use). If reportlab
    is not available, logs a warning and returns None.
    """
    try:
        (
            SimpleDocTemplate,
            A4,
            getSampleStyleSheet,
            ParagraphStyle,
            inch,
            TA_CENTER,
            RLImage,
            PageBreak,
            Paragraph,
            Spacer,
        ) = _get_reportlab_flowables()
    except ImportError as e:
        logger.warning(
            "reportlab is not installed; skipping all-charts PDF. %s "
            "Install reportlab to generate summary/all_charts.pdf.",
            e,
        )
        return None

    by_module = collect_charts_by_module(run_root)
    if not by_module:
        logger.debug("No chart images found under %s; skipping PDF.", run_root)
        return None

    total_charts = sum(len(paths) for paths in by_module.values())
    # Stable order: normal modules first (alphabetically), then summary/assets/debug last
    module_names = sorted(
        by_module.keys(),
        key=lambda m: (m in _TAIL_MODULES, m),
    )

    output_pdf_path = Path(output_pdf_path)
    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_pdf_path),
        pagesize=A4,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    title_style = styles["Heading1"]
    heading_style = styles["Heading2"]
    caption_style = ParagraphStyle(
        "Caption",
        parent=styles["Normal"],
        fontSize=8,
        alignment=TA_CENTER,
    )
    flowables = []
    page_width_pts = A4[0] - 1.5 * inch

    # Cover page
    normal_style = styles["Normal"]
    run_name = run_root.name
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    flowables.append(Paragraph("Charts Summary", title_style))
    flowables.append(Spacer(1, 0.3 * inch))
    flowables.append(Paragraph(f"Run: {run_name}", normal_style))
    flowables.append(Paragraph(f"Generated: {ts}", normal_style))
    flowables.append(Paragraph(f"Modules: {len(module_names)} — Charts: {total_charts}", normal_style))
    flowables.append(Spacer(1, 0.5 * inch))
    flowables.append(PageBreak())

    for module in module_names:
        paths = by_module[module]
        title = _module_display_name(module)
        flowables.append(Paragraph(title, heading_style))
        flowables.append(Spacer(1, 0.2 * inch))

        for path in paths:
            try:
                img = _image_flowable(path, page_width_pts, RLImage)
                if img is not None:
                    img.hAlign = "CENTER"
                    flowables.append(img)
                    # Caption: filename or short relative path (escape for XML)
                    try:
                        rel = path.relative_to(run_root)
                        caption_text = rel.as_posix()
                    except ValueError:
                        caption_text = path.name
                    caption_text = caption_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    flowables.append(Paragraph(caption_text, caption_style))
                    flowables.append(Spacer(1, 0.15 * inch))
            except Exception as e:
                logger.debug("Skipping image %s: %s", path, e)

        flowables.append(Spacer(1, 0.2 * inch))
        flowables.append(PageBreak())

    try:
        doc.build(flowables)
    except Exception as e:
        logger.warning("Failed to build charts PDF: %s", e)
        return None

    logger.info(
        "Saved all-charts PDF to %s (%d modules, %d charts)",
        output_pdf_path,
        len(module_names),
        total_charts,
    )
    return output_pdf_path


def _module_display_name(module: str) -> str:
    """Human-readable section title for a module directory name."""
    replacements = {
        "entity_sentiment": "Entity sentiment",
        "qa_analysis": "Q&A analysis",
        "semantic_similarity_advanced": "Semantic similarity",
        "voice": "Voice / prosody",
        "wordclouds": "Word clouds",
        "ner": "Named entities",
        "affect_tension": "Affect & tension",
        "prosody_dashboard": "Prosody dashboard",
        "voice_charts_core": "Voice charts",
    }
    return replacements.get(module, module.replace("_", " ").title())


def _image_flowable(
    image_path: Path, max_width_pts: float, rl_image_class: Any
) -> Any:
    """Create a reportlab Image flowable that fits within max_width_pts (PDF points).

    Uses Pillow to read DPI when present and converts pixels to points correctly.
    Never upscales: if the image is small, we use its natural size in points.
    """
    path = Path(image_path)
    if not path.exists():
        return None
    try:
        from PIL import Image as PILImage
        pil = PILImage.open(path)
        width_px, height_px = pil.size
        dpi = pil.info.get("dpi")
        if isinstance(dpi, (int, float)):
            dpi = (float(dpi), float(dpi))
        elif isinstance(dpi, tuple) and len(dpi) >= 2:
            dpi = (float(dpi[0]), float(dpi[1]))
        else:
            dpi = None
        pil.close()
    except Exception:
        return None
    if width_px <= 0:
        return None
    width_pt, height_pt = _pixels_to_points(width_px, height_px, dpi)
    # Fit to page width, but never upscale
    if width_pt > max_width_pts:
        scale = max_width_pts / width_pt
        width_pt = max_width_pts
        height_pt *= scale
    return rl_image_class(str(path), width=width_pt, height=height_pt)
