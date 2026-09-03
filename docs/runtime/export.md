# Exporting runs (ZIP, HTML, EPUB)

How Overview / Artifacts export packages selected run artifacts for offline use.

**Related:** [output layout contract](../contracts/output-contract-v1.md), [output conventions](../dev/output_conventions.md), [known limitations](../known_limitations.md) (EPUB / interactive charts).

## What you get

From **Overview** or **Artifacts**, choose artifacts and download a ZIP. The ZIP contains:

1. **Selected files** — copies of the artifacts you chose (transcript JSON, module data, charts, summaries, …).
2. **`index.html`** — a self-contained reading page built from that **same selection** (transcript view, prose summaries when present, charts gallery). Opens over `file://`.
3. **`index.epub`** — the same informational package as an ebook, when `ebooklib` is installed (see below). Written beside `index.html`; missing dependency or build failure does **not** fail the ZIP of raw files.

**Parity is selection-scoped:** HTML and EPUB only include content resolvable from the artifacts copied into that ZIP — not an automatic full-run book.

### Charts-only export

The Charts page “export visible charts” path remains a **charts ZIP + `index.html` only** (no EPUB).

## Content of `index.html` / `index.epub`

| Section | Source | EPUB notes |
|---------|--------|------------|
| Transcript | Selected / resolvable transcript JSON | Speaker-grouped turns + shared metadata |
| Summaries | Selected summary MD/JSON (LLM, narrative, action items / meeting extracts, speaker summaries, …) | Includes model / provider / truncated provenance when present |
| Charts | Selected `chart_static` / `chart_dynamic` | Static rasters embedded when valid (PNG/JPEG/WebP/GIF); interactive HTML charts become title/meta/description notes (not runnable iframes) |

Generated presentation files (`index.html`, `index.epub`, other `*.epub`) are **not** treated as transcript/summary/chart inputs if re-selected in a later export.

## Hard-cap

Export enforces a size cap on **selected source artifact bytes** before staging. Generated `index.html` / `index.epub` are **exempt** from that pre-check (EPUB may re-embed static chart images already in the ZIP).

## Dependency (`ebooklib`)

EPUB packaging uses optional **`ebooklib`**, declared on the **`visualization`** extra (also in **`[full]`**):

```bash
pip install -e '.[visualization]'
# or
pip install -e '.[full]'
```

Docker / `requirements.txt` images include `ebooklib` with the visualization stack. Without it, ZIP + `index.html` still work; `index.epub` is skipped with a log warning.

## Pipeline vs export

Human-readable **TXT / CSV / SRT / WebVTT** from the `transcript_output` module are ordinary run artifacts. Full HTML/EPUB packages are produced at **export time** from the completed run’s selected artifacts — not as an early pipeline writer that claims summaries/charts before they exist.

Persistent per-run `.epub` registration on disk (outside ZIP export) is not shipped in this release.
