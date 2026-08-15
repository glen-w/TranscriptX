"""EPUB export builder (Overview export parity with index.html)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

from transcriptx.core.utils.logger import get_logger
from transcriptx.export.epub_xhtml import (
    ChapterIdAllocator,
    provenance_meta_bits,
    summary_markdown_to_xhtml,
    wrap_epub_xhtml,
    xml_escape,
)
from transcriptx.export.grouping import group_contiguous_segments_by_speaker
from transcriptx.export.resolve import normalize_transcript_payload
from transcriptx.export.transcript_meta import (
    format_transcript_meta_bits,
    transcript_export_meta,
)
from transcriptx.export.types import (
    ChartModuleGroup,
    ExportTextSummary,
    ResolvedExportBundle,
)
from transcriptx.utils.text_utils import format_time_detailed

logger = get_logger()

EPUB_CSS = """\
body { font-family: serif; line-height: 1.45; margin: 1.2em; }
h1, h2, h3 { font-family: sans-serif; }
.meta { color: #444; font-size: 0.9em; }
.tx-speaker { font-weight: bold; font-family: sans-serif; }
.tx-time { color: #555; font-size: 0.85em; margin-left: 0.5em; }
.tx-segment { margin: 1em 0; }
.chart-card { margin: 1.2em 0; padding-bottom: 0.8em; border-bottom: 1px solid #ddd; }
.chart-card img { max-width: 100%; height: auto; }
.note { font-style: italic; color: #555; }
"""

_STATIC_IMAGE_MIME: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"
_GIF_MAGIC = b"GIF8"
_WEBP_RIFF = b"RIFF"
_WEBP_WEBP = b"WEBP"


@dataclass
class EpubImageAsset:
    internal_href: str
    mime: str
    data: bytes


@dataclass
class EpubChapter:
    chapter_id: str
    title: str
    href: str
    xhtml: str


@dataclass
class EpubDocumentPlan:
    """Deterministic EPUB contents before ebooklib packaging."""

    title: str
    language: str
    chapters: list[EpubChapter] = field(default_factory=list)
    images: list[EpubImageAsset] = field(default_factory=list)
    css: str = EPUB_CSS


def _format_timestamp_range(start: Any, end: Any) -> str:
    try:
        return (
            f"{format_time_detailed(float(start))} - {format_time_detailed(float(end))}"
        )
    except (TypeError, ValueError):
        return ""


def is_speaker_summary(summary: ExportTextSummary) -> bool:
    title = str(summary.get("title") or "")
    section_id = str(summary.get("section_id") or "")
    return (
        title.startswith("Speaker Summary")
        or "llm_speaker_summary" in section_id
        or "llm-speaker-summary" in section_id
    )


def resolve_static_image(
    path: Optional[Path],
) -> tuple[Optional[bytes], Optional[str]]:
    """Return (bytes, mime) for an eligible static chart image, else (None, None)."""
    if path is None:
        return None, None
    try:
        if not path.is_file():
            return None, None
        suffix = path.suffix.lower()
        mime = _STATIC_IMAGE_MIME.get(suffix)
        if mime is None:
            return None, None
        data = path.read_bytes()
        if not data:
            return None, None
        if mime == "image/png" and not data.startswith(_PNG_MAGIC):
            return None, None
        if mime == "image/jpeg" and not data.startswith(_JPEG_MAGIC):
            return None, None
        if mime == "image/gif" and not data.startswith(_GIF_MAGIC):
            return None, None
        if mime == "image/webp":
            if not (
                data.startswith(_WEBP_RIFF)
                and len(data) >= 12
                and data[8:12] == _WEBP_WEBP
            ):
                return None, None
        return data, mime
    except OSError:
        return None, None


def _stable_image_name(
    preferred: str,
    *,
    used: set[str],
    suffix: str,
) -> str:
    base = Path(preferred).stem or "chart"
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in base).strip("-")
    if not safe:
        safe = "chart"
    name = f"{safe}{suffix}"
    n = 2
    while name in used:
        name = f"{safe}-{n}{suffix}"
        n += 1
    used.add(name)
    return name


def plan_export_epub(
    *,
    page_title: str,
    transcript_data: Optional[dict[str, Any]] = None,
    text_summaries: Optional[Sequence[ExportTextSummary]] = None,
    chart_groups: Optional[Sequence[ChartModuleGroup]] = None,
) -> Optional[EpubDocumentPlan]:
    """Build a deterministic EPUB document plan (no ebooklib required)."""
    ids = ChapterIdAllocator()
    chapters: list[EpubChapter] = []
    images: list[EpubImageAsset] = []
    image_names: set[str] = set()

    language = "en"
    normalized = normalize_transcript_payload(transcript_data)
    meta = transcript_export_meta(normalized) if normalized is not None else None
    if meta and meta.language:
        language = str(meta.language)

    # Title page
    title_id = ids.allocate("title", fallback="title")
    title_bits = format_transcript_meta_bits(meta) if meta else []
    title_body_parts = [f"<h1>{xml_escape(page_title)}</h1>"]
    if title_bits:
        title_body_parts.append(
            '<p class="meta">'
            + " · ".join(xml_escape(bit) for bit in title_bits)
            + "</p>"
        )
    chapters.append(
        EpubChapter(
            chapter_id=title_id,
            title=page_title,
            href=f"{title_id}.xhtml",
            xhtml=wrap_epub_xhtml(title=page_title, body="\n".join(title_body_parts)),
        )
    )

    # Transcript (isolated)
    try:
        if normalized is not None:
            segments = normalized.get("segments") or []
            body_parts = ['<h1 id="transcript">Transcript</h1>']
            if meta is not None:
                body_parts.append(
                    '<p class="meta">'
                    + " · ".join(
                        xml_escape(bit) for bit in format_transcript_meta_bits(meta)
                    )
                    + "</p>"
                )
            for speaker_name, group_segments in group_contiguous_segments_by_speaker(
                segments
            ):
                group_start = group_segments[0].get("start", 0)
                group_end = group_segments[-1].get("end", 0)
                timestamp = _format_timestamp_range(group_start, group_end)
                time_html = (
                    f'<span class="tx-time">{xml_escape(timestamp)}</span>'
                    if timestamp
                    else ""
                )
                texts = "".join(
                    f"<p>{xml_escape(str(segment.get('text', '')))}</p>"
                    for segment in group_segments
                    if str(segment.get("text", "")).strip()
                )
                body_parts.append(
                    '<div class="tx-segment">'
                    f'<p><span class="tx-speaker">{xml_escape(speaker_name)}</span>'
                    f"{time_html}</p>"
                    f"{texts}</div>"
                )
            chap_id = ids.allocate("transcript", fallback="transcript")
            chapters.append(
                EpubChapter(
                    chapter_id=chap_id,
                    title="Transcript",
                    href=f"{chap_id}.xhtml",
                    xhtml=wrap_epub_xhtml(
                        title="Transcript", body="\n".join(body_parts)
                    ),
                )
            )
    except Exception as exc:
        logger.warning("EPUB transcript section failed: %s", exc)

    # Summaries (isolated per chapter; whole summaries group failure drops only those)
    summary_items = [s for s in (text_summaries or ()) if s.get("body")]
    for summary in summary_items:
        try:
            preferred = str(summary.get("section_id") or summary.get("title") or "summary")
            chap_id = ids.allocate(preferred, fallback="summary")
            title = str(summary.get("title") or "Summary")
            body_md = str(summary.get("body") or "")
            body_xhtml = summary_markdown_to_xhtml(body_md)
            if not body_xhtml and body_md.strip():
                body_xhtml = f"<p>{xml_escape(body_md)}</p>"
            prov_bits = provenance_meta_bits(summary.get("provenance"))
            prov_html = ""
            if prov_bits:
                prov_html = (
                    '<p class="meta">'
                    + " · ".join(xml_escape(bit) for bit in prov_bits)
                    + "</p>"
                )
            body = f"<h1>{xml_escape(title)}</h1>\n{body_xhtml}\n{prov_html}"
            chapters.append(
                EpubChapter(
                    chapter_id=chap_id,
                    title=title,
                    href=f"{chap_id}.xhtml",
                    xhtml=wrap_epub_xhtml(title=title, body=body),
                )
            )
        except Exception as exc:
            logger.warning("EPUB summary chapter failed: %s", exc)

    # Charts (isolated per module / card)
    try:
        for group in chart_groups or ():
            try:
                chap_id = ids.allocate(group.anchor_id, fallback="charts")
                parts = [f"<h1>{xml_escape(group.module_name)}</h1>"]
                for card in group.cards:
                    parts.append('<div class="chart-card">')
                    parts.append(f"<h2>{xml_escape(card.title)}</h2>")
                    parts.append(f'<p class="meta">{xml_escape(card.meta)}</p>')
                    if card.description:
                        parts.append(f"<p>{xml_escape(card.description)}</p>")
                    if card.kind == "static":
                        data, mime = resolve_static_image(card.source_path)
                        if data and mime and card.source_path is not None:
                            suffix = card.source_path.suffix.lower() or ".png"
                            fname = _stable_image_name(
                                card.display_relpath or card.title,
                                used=image_names,
                                suffix=suffix,
                            )
                            href = f"images/{fname}"
                            images.append(
                                EpubImageAsset(
                                    internal_href=href, mime=mime, data=data
                                )
                            )
                            parts.append(
                                f'<p><img src="{xml_escape(href)}" '
                                f'alt="{xml_escape(card.title)}" /></p>'
                            )
                        else:
                            parts.append(
                                '<p class="note">Static chart image unavailable '
                                "or unsupported.</p>"
                            )
                    else:
                        display = card.display_relpath or "interactive chart"
                        parts.append(
                            '<p class="note">Interactive HTML chart is not '
                            "embeddable in EPUB "
                            f"(source: {xml_escape(display)}).</p>"
                        )
                    if card.llm_description:
                        parts.append(f"<p>{xml_escape(card.llm_description)}</p>")
                    parts.append("</div>")
                chapters.append(
                    EpubChapter(
                        chapter_id=chap_id,
                        title=group.module_name,
                        href=f"{chap_id}.xhtml",
                        xhtml=wrap_epub_xhtml(
                            title=group.module_name, body="\n".join(parts)
                        ),
                    )
                )
            except Exception as exc:
                logger.warning(
                    "EPUB chart module %s failed: %s", group.module_name, exc
                )
    except Exception as exc:
        logger.warning("EPUB charts section failed: %s", exc)

    # Title-only book is not useful if nothing else rendered — still allow title
    # when at least transcript/summaries/charts exist beyond the title page.
    content_chapters = [c for c in chapters if c.chapter_id != title_id]
    if not content_chapters:
        # Keep title-only only if we somehow have no content; mirror HTML None
        return None

    return EpubDocumentPlan(
        title=page_title,
        language=language,
        chapters=chapters,
        images=images,
        css=EPUB_CSS,
    )


def write_epub_from_plan(plan: EpubDocumentPlan, output_path: Path) -> Path:
    """Package an EpubDocumentPlan with ebooklib. Raises ImportError if missing."""
    from transcriptx.core.utils.lazy_imports import get_ebooklib
    from ebooklib import epub

    get_ebooklib()  # validate import / hint

    book = epub.EpubBook()
    book.set_identifier(f"transcriptx-{plan.title}")
    book.set_title(plan.title)
    book.set_language(plan.language or "en")
    book.add_author("TranscriptX")

    css_item = epub.EpubItem(
        uid="style",
        file_name="styles.css",
        media_type="text/css",
        content=plan.css.encode("utf-8"),
    )
    book.add_item(css_item)

    spine_items: list[Any] = ["nav"]
    toc: list[Any] = []
    for chapter in plan.chapters:
        item = epub.EpubHtml(
            title=chapter.title,
            file_name=chapter.href,
            lang=plan.language or "en",
        )
        item.content = chapter.xhtml.encode("utf-8")
        item.add_item(css_item)
        book.add_item(item)
        spine_items.append(item)
        toc.append(item)

    for image in plan.images:
        book.add_item(
            epub.EpubItem(
                uid=f"img-{Path(image.internal_href).stem}",
                file_name=image.internal_href,
                media_type=image.mime,
                content=image.data,
            )
        )

    book.toc = tuple(toc)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine_items

    output_path.parent.mkdir(parents=True, exist_ok=True)
    epub.write_epub(str(output_path), book)
    return output_path


def build_export_epub(
    *,
    output_path: Path,
    page_title: str = "Export",
    transcript_data: Optional[dict[str, Any]] = None,
    text_summaries: Optional[Sequence[ExportTextSummary]] = None,
    chart_groups: Optional[Sequence[ChartModuleGroup]] = None,
    bundle: Optional[ResolvedExportBundle] = None,
) -> Optional[Path]:
    """Build Overview-export ``index.epub``. Returns path or None when empty/unavailable."""
    if bundle is not None:
        page_title = bundle.page_title
        transcript_data = bundle.transcript_data
        text_summaries = bundle.text_summaries
        chart_groups = bundle.chart_groups

    plan = plan_export_epub(
        page_title=page_title,
        transcript_data=transcript_data,
        text_summaries=text_summaries,
        chart_groups=chart_groups,
    )
    if plan is None:
        return None

    try:
        return write_epub_from_plan(plan, output_path)
    except ImportError as exc:
        logger.warning("EPUB dependency unavailable (ebooklib): %s", exc)
        return None
    except Exception as exc:
        logger.warning("EPUB build failed: %s", exc)
        return None

