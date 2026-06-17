"""
Charts gallery export helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import html
import shutil
import tempfile
from collections import defaultdict

from transcriptx.web.models.artifact import Artifact
from transcriptx.web.services.artifact_service import ArtifactService, HARD_CAP_BYTES
from transcriptx.web.services.chart_view_model_service import resolve_chart_description


@dataclass(frozen=True)
class ChartsExportResult:
    bytes: bytes
    filename: str
    exported_count: int
    omitted_count: int
    module_count: int


@dataclass(frozen=True)
class _ExportableItem:
    artifact: Artifact
    source_path: Path
    export_rel_path: Path
    size_bytes: int


def _export_rel_path_for_chart(artifact: Artifact) -> Path:
    if artifact.storage_root:
        return Path(artifact.id[:16]) / artifact.rel_path
    return Path(artifact.rel_path)


def _resolve_exportable(
    run_root: Path, charts: list[Artifact]
) -> list[_ExportableItem]:
    items: list[_ExportableItem] = []
    for artifact in charts:
        source = ArtifactService.resolve_artifact_source_path(run_root, artifact)
        if source is None:
            continue
        try:
            size_bytes = source.stat().st_size
        except OSError:
            size_bytes = int(artifact.bytes or 0)
        items.append(
            _ExportableItem(
                artifact=artifact,
                source_path=source,
                export_rel_path=_export_rel_path_for_chart(artifact),
                size_bytes=size_bytes,
            )
        )
    return items


def _sort_key(item: _ExportableItem) -> tuple[str, str]:
    module = item.artifact.module or "Other"
    return (module.lower(), item.artifact.rel_path)


# Shared inline CSS for self-contained export index pages (charts gallery and the
# combined Overview export index). Kept renderer-agnostic and CDN-free so exports
# render correctly when opened directly from disk over file://.
_EXPORT_INDEX_CSS = (
    "body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"
    "background:#f6f7f9;color:#15171a;}main{display:grid;grid-template-columns:240px 1fr;"
    "gap:20px;max-width:1400px;margin:0 auto;padding:24px;}nav{position:sticky;top:16px;"
    "align-self:start;background:#fff;border:1px solid #dde2e8;border-radius:10px;padding:14px;}"
    "nav ul{margin:8px 0 0;padding-left:18px;}nav a{text-decoration:none;color:#0f3d91;}"
    ".content h1{margin:0 0 14px;}.notice{background:#fff7db;border:1px solid #f0d37a;"
    "padding:10px 12px;border-radius:8px;margin-bottom:14px;}.card-grid{display:grid;"
    "grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px;}.card{background:#fff;"
    "border:1px solid #dde2e8;border-radius:10px;padding:12px;display:flex;flex-direction:column;"
    "gap:8px;}.card h3{margin:0;font-size:16px;}.meta{margin:0;color:#5a6473;font-size:13px;}"
    ".card img{width:100%;height:auto;max-width:100%;border-radius:8px;border:1px solid #e6eaf0;display:block;}"
    ".chart-thumb{display:block;cursor:zoom-in;}.chart-thumb:hover img{border-color:#0f3d91;"
    "box-shadow:0 0 0 2px rgba(15,61,145,0.15);}"
    ".card h3{display:flex;align-items:center;gap:6px;}.tx-info{position:relative;display:inline-flex;"
    "align-items:center;justify-content:center;width:16px;height:16px;color:#5a6473;font-size:14px;"
    "cursor:help;outline:none;}.tx-info:hover,.tx-info:focus{color:#0f3d91;}.tx-tooltip{visibility:hidden;"
    "opacity:0;position:absolute;left:50%;bottom:calc(100% + 8px);transform:translateX(-50%);"
    "width:max-content;max-width:260px;background:#15171a;color:#fff;font-size:12px;font-weight:400;"
    "line-height:1.4;text-align:left;padding:8px 10px;border-radius:8px;box-shadow:0 4px 12px "
    "rgba(0,0,0,0.18);z-index:10;transition:opacity .12s ease;pointer-events:none;}"
    ".tx-tooltip::after{content:'';position:absolute;top:100%;left:50%;transform:translateX(-50%);"
    "border:5px solid transparent;border-top-color:#15171a;}.tx-info:hover .tx-tooltip,"
    ".tx-info:focus .tx-tooltip{visibility:visible;opacity:1;}"
    ".badge{display:inline-block;width:max-content;padding:2px 8px;border-radius:999px;"
    "background:#e8eefc;color:#123b8c;font-size:12px;}.open-link{font-size:13px;font-weight:600;}"
    ".card iframe{width:100%;height:320px;border:1px solid #e1e6ee;border-radius:8px;}"
    ".hint{font-size:12px;color:#5a6473;margin:0;}section{margin-bottom:24px;}"
    ".tx-segment{background:#fff;border:1px solid #dde2e8;border-radius:10px;padding:10px 12px;"
    "margin-bottom:10px;}.tx-speaker-chip{display:inline-block;padding:2px 10px;border-radius:999px;"
    "background:#e8eefc;color:#123b8c;font-weight:600;font-size:13px;}.tx-time{color:#5a6473;"
    "font-size:12px;margin-left:6px;}.tx-text{margin:6px 0 0;white-space:pre-wrap;}"
    ".tx-summary{background:#fff;border:1px solid #dde2e8;border-radius:10px;padding:12px 14px;"
    "margin-bottom:10px;}"
    ".included-files{font-size:13px;color:#5a6473;}.included-files ul{margin:6px 0 0;padding-left:18px;}"
    "@media (max-width: 900px){main{grid-template-columns:1fr;}nav{position:static;}}"
)


def render_chart_sections(
    items: list[_ExportableItem],
) -> tuple[list[str], list[str]]:
    """Build the per-module TOC entries and chart gallery `<section>` markup.

    Returns a tuple of (toc_entries, section_html). Shared by the charts-only
    export index and the combined Overview export index.
    """
    grouped: dict[str, list[_ExportableItem]] = defaultdict(list)
    for item in sorted(items, key=_sort_key):
        grouped[item.artifact.module or "Other"].append(item)
    ordered_modules = sorted(grouped.keys(), key=str.lower)

    toc_entries: list[str] = []
    section_html: list[str] = []
    for module_name in ordered_modules:
        anchor = f"module-{module_name.lower().replace(' ', '-')}"
        toc_entries.append(
            f'<li><a href="#{html.escape(anchor, quote=True)}">'
            f"{html.escape(module_name)}</a></li>"
        )
        cards: list[str] = []
        for item in grouped[module_name]:
            artifact = item.artifact
            rel = item.export_rel_path.as_posix()
            title = artifact.title or Path(artifact.rel_path).name
            meta = f"{artifact.kind} · {artifact.scope or '—'}"
            if artifact.kind == "chart_static":
                body = (
                    f'<a class="chart-thumb" href="{html.escape(rel, quote=True)}" '
                    f'title="Open {html.escape(title, quote=True)}">'
                    f'<img src="{html.escape(rel, quote=True)}" '
                    f'alt="{html.escape(title, quote=True)}" loading="lazy" />'
                    "</a>"
                )
            else:
                body = (
                    '<span class="badge">Interactive HTML</span>'
                    f'<a class="open-link" href="{html.escape(rel, quote=True)}">'
                    "Open chart</a>"
                    f'<iframe title="{html.escape(title, quote=True)}" '
                    f'src="{html.escape(rel, quote=True)}"></iframe>'
                    '<p class="hint">Inline preview is best effort for local files.</p>'
                )
            info_icon = ""
            description = resolve_chart_description(artifact)
            if description:
                info_icon = (
                    '<span class="tx-info" tabindex="0" role="img" '
                    f'aria-label="{html.escape(description, quote=True)}">'
                    "&#9432;"
                    f'<span class="tx-tooltip">{html.escape(description)}</span>'
                    "</span>"
                )
            cards.append(
                '<article class="card">'
                f"<h3>{html.escape(title)}{info_icon}</h3>"
                f'<p class="meta">{html.escape(meta)}</p>'
                f"{body}"
                "</article>"
            )
        section_html.append(
            f'<section id="{html.escape(anchor, quote=True)}">'
            f"<h2>{html.escape(module_name)}</h2>"
            '<div class="card-grid">' + "".join(cards) + "</div></section>"
        )
    return toc_entries, section_html


def generate_charts_index_html(
    items: list[_ExportableItem], omitted_count: int, run_title: str
) -> str:
    toc_entries, section_html = render_chart_sections(items)

    omitted_banner = ""
    if omitted_count > 0:
        plural = "s" if omitted_count != 1 else ""
        omitted_banner = (
            '<div class="notice">'
            f"{omitted_count} chart{plural} were unavailable and omitted from this export."
            "</div>"
        )

    return (
        "<!DOCTYPE html>"
        "<html><head><meta charset='utf-8'/>"
        f"<title>Charts Export - {html.escape(run_title)}</title>"
        "<style>" + _EXPORT_INDEX_CSS + "</style></head><body>"
        "<main><nav><strong>Modules</strong><ul>"
        + "".join(toc_entries)
        + "</ul></nav><div class='content'>"
        f"<h1>Charts Export: {html.escape(run_title)}</h1>"
        + omitted_banner
        + "".join(section_html)
        + "</div></main></body></html>"
    )


def prepare_charts_export_zip(
    run_root: Path, charts: list[Artifact], run_id: str
) -> ChartsExportResult:
    items = _resolve_exportable(run_root, charts)
    omitted_count = max(0, len(charts) - len(items))
    total_bytes = sum(item.size_bytes for item in items)
    if total_bytes > HARD_CAP_BYTES:
        raise ValueError("Export exceeds hard cap.")

    staging_dir = Path(tempfile.mkdtemp(prefix="tx_charts_export_"))
    zip_temp_dir = Path(tempfile.mkdtemp(prefix="tx_charts_zip_"))
    zip_file = zip_temp_dir / f"{run_id}_charts.zip"

    try:
        for item in items:
            target = staging_dir / item.export_rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item.source_path, target)

        index_html = generate_charts_index_html(items, omitted_count, run_id)
        (staging_dir / "index.html").write_text(index_html, encoding="utf-8")
        shutil.make_archive(str(zip_file).replace(".zip", ""), "zip", staging_dir)
        payload = zip_file.read_bytes()
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)
        try:
            zip_file.unlink(missing_ok=True)
        except TypeError:
            if zip_file.exists():
                zip_file.unlink()
        shutil.rmtree(zip_temp_dir, ignore_errors=True)

    module_names = {item.artifact.module or "Other" for item in items}
    return ChartsExportResult(
        bytes=payload,
        filename=f"{run_id}_charts.zip",
        exported_count=len(items),
        omitted_count=omitted_count,
        module_count=len(module_names),
    )
