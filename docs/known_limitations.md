# Known limitations

Limits that affect everyday use: optional modules, large libraries, voice features, local AI, and export. This is the public summary — link here instead of restating these claims. Deeper notes stay in developer docs.

## Experimental analyses

Some modules are experimental classifiers or heuristics (notably **contextual emotion** and **fine-grained emotion**). They are kept off Balanced defaults; opt in via Thorough / Custom presets if you want them. Outputs are not definitive affect labels.

## Optional BERTopic and compiled dependencies

BERTopic requires the optional `[bertopic]` (or `[full]`) stack (`bertopic` / `hdbscan` / `umap-learn`). Core installs deliberately omit that stack so clean installs are not blocked by `umap-learn` → `numba` → `llvmlite` source builds on some hosts (especially certain **macOS arm64** environments without usable wheels).

Without the extra, the module stays listed and runs report a stable `missing_extra:bertopic` / `broken_extra:bertopic` skip — the pipeline continues. Docker / `requirements.txt` images still ship the fuller stack where the image build succeeds.

See [bertopic_optional_module.md](dev/bertopic_optional_module.md) and the [install verification matrix](runtime/install_verification_matrix.md).

## Large library / performance measurements

Documented corpus sizes and a measurement recipe ship in developer performance envelopes. **Large-library UI soak** passed on maintainer hardware (2026-08-07): UI remained responsive with **200+** library transcripts. **Medium-corpus Balanced** batch also measured 2026-08-07 (~9.3 min wall for 6 transcripts on Docker Compose; all succeeded) — see [performance_envelopes_1_0.md](dev/performance_envelopes_1_0.md) and [manual_acceptance_1_0.md](dev/manual_acceptance_1_0.md) §3.12.

## Voice identity privacy

Voice fingerprint / speaker-match features are identity-sensitive. Read the in-app voice privacy notice before enabling. Local processing does not remove the sensitivity of biometric-like embeddings stored on disk.

Optional **auto-name / auto-link** on ingest writes display names and may create `auto_identified` profile links when fusion is confident. It does not enrol new voice samples. Thresholds remain provisional; conflicts and collisions leave `SPEAKER_*` labels. Style-only apply is off by default. Operator guide: [auto-identify.md](runtime/auto-identify.md).

## Stochastic Local AI output

Optional Ollama / Local AI modules are stochastic. Re-runs can differ. Artifacts carry model identity fields where available; treat Local AI text as assistive, not ground truth. Principal surfaces label Local AI vs deterministic summaries.

## Content rename suggestions

Optional assistive stems on **Rename Transcript** / import rename forms (`input.rename_content_suggestions=auto`). Default is **off**.

- **Not authoritative:** Dates and titles are heuristics (transcript regex, optional local LLM, optional web snippet parse). Webinars without an explicit date in the file or dialogue may stay title-only or show a weak **file date** (import/mtime) — that is not the event date.
- **Web lookup** (`input.rename_suggest_web`) is off by default, requires network, and only runs for public-event-like filenames or dialogue. It sends a short search query built from title cues, not the transcript body.
- **LLM** uses consumer `rename_suggestions` and `rename_suggestions_effort`; thinking-family models are skipped for JSON safety (same policy as other JSON consumers — see [llm.md](runtime/llm.md)).
- Nothing renames until you submit **Rename**; import auto-apply still uses device-filename smart rename only.

Settings: [settings.md](runtime/settings.md#content-rename-suggestions-assistive). Walkthrough: [rename-transcript.md](workflows/rename-transcript.md).

## Overview export EPUB

Full behaviour: [runtime/export.md](runtime/export.md).

Overview artifact ZIP export writes ``index.epub`` beside ``index.html`` when the
optional ``ebooklib`` dependency is available (``pip install -e '.[visualization]'``
or ``.[full]``; also in Docker / ``requirements.txt`` images). Content is
**selection-scoped** — the same artifacts copied into the ZIP that feed the HTML
index — not a silent full-run book.

Static chart rasters (PNG/JPEG/WebP/GIF) are embedded when valid; interactive
HTML charts appear as captions/notes only (e-readers cannot run them). Generated
``index.html`` / ``index.epub`` files are exempt from the ZIP source hard-cap and
are excluded from feeding subsequent export resolvers if re-selected.

Charts-only ZIP export remains HTML-only (no EPUB) in this release.

## Speaker ID / Corrections Components v2 workspaces

Speaker Identification, Corrections Studio review, Correct-mode word
selection, and Theme D transcript reader run in the ``transcriptx-workspaces``
package (Docker images and ``pip install -e ".[web]"`` from a git checkout).
Speaker ID has **no classic widget fallback**; a missing package shows an
install error. Corrections Studio review can roll back with
``TX_CORRECTIONS_WORKSPACE_COMPONENT=0``. See
[theme_c_workspaces_ccv2.md](dev/theme_c_workspaces_ccv2.md).

## Theme D reader (full-file playback)

The Transcript **reader workspace** plays the resolved source audio via a
loopback HTTP route (``127.0.0.1`` only). Non-loopback ``TRANSCRIPTX_HOST``
values disable the route; the reader shows an unavailable message. HTTPS
Streamlit without a compatible media URL cannot load ``http://127.0.0.1`` audio.
Roll back to clip karaoke with ``TX_READER_WORKSPACE_COMPONENT=0``. Very large
transcripts may omit word timings in the reader payload while keeping segment
playback. Correct mode uses the clip player, not the reader.

## Install honesty (Mac MPS)

Native **Apple MPS** is **supported-with-caveats**, not universally validated for every optional model. Prefer **Docker CPU** for predictable installs. If MPS initialisation or model execution fails, use `TRANSCRIPTX_FORCE_CPU=1` (documented in [installation.md](runtime/installation.md)). Do not assume every optional model runs reliably on MPS.

