# Workflow walkthrough media capture

Maintainer notes for regenerating screenshots and GIFs under `docs/_static/workflows/`.

## Sample corpus

| Item | Value |
|------|-------|
| Fixture | [`docs/workflows/fixtures/planning_review.json`](../workflows/fixtures/planning_review.json) |
| Provenance | Synthetic authored text for docs; not a real recording |
| Speakers | `SPEAKER_00` / `SPEAKER_01` / `SPEAKER_02` (name to Maya / Jordan / Sam in walkthrough 2) |
| Suggested names | Maya (facilitator), Jordan (engineering), Sam (support) |

Import via **Import Transcript**. Do not commit managed library copies under `data/`.

Committed stills (October 2026) are a **Balanced** run of *Rapid Response Webinar Analysing the Biodiversity Beyond National Jurisdiction Treaty* on package 0.9.9.5, with display names assigned before analysis. The practice fixture for the written steps remains `planning_review.json`. Recapture against a disposable data root; do not commit library copies or host paths.

## Application state

Capture against a disposable data root when practical.

| Walkthrough media | Expected state |
|-------------------|----------------|
| Import / Run Analysis | Fresh import; no requirement for prior runs |
| Overview / Insights / Export / Charts | Completed **Balanced** run on the fixture (re-run after naming if speaker cards should show names) |
| Speaker Identification | Fixture selected; speakers still diarized or mid-naming |
| Local AI | `llm.enabled` with reachable Ollama; modules `llm_summary` + `llm_action_items` completed |
| Groups | At least one managed transcript; create via Groups expander |
| Corrections | Transcript VIEW with Correct mode; unique find text in a segment |
| Rename Transcript | Managed transcript selected on Rename page |
| Speakers | At least one longitudinal profile (link from Speaker ID) |
| Export HTML preview | Unpacked ZIP `index.html` opened at `file://` (crop to page content) |

## Viewport and chrome

- Browser window **1440×900** (or device pixel ratio 1 with that CSS viewport).
- Capture the Streamlit app pane only — no OS desktop, no browser URL bar if avoidable.
- Prefer tight crops around the meaningful region (sidebar + main panel, or main panel alone).
- Scrub usernames, absolute host paths, tokens, and personal transcript titles before committing.

## Routes (sidebar labels)

| Asset stem | Sidebar page |
|------------|--------------|
| `first-analysis-import` | Import Transcript |
| `first-analysis-run-analysis` | Run Analysis |
| `first-analysis-overview` | Overview |
| `speaker-identification-*` (legacy `speaker-trust-*`) | Speaker Identification / Transcript |
| `investigate-*` | Overview / Insights (Highlights) / Transcript |
| `local-ai-*` | Run Analysis (LLM setup) / Overview / Insights (Actions) |
| `export-*` | Artifacts (Browse / Export) + external HTML preview |
| `charts-*` | Charts |
| `groups-*` | Groups |
| `corrections-*` | Transcript (Correct mode) / Corrections Studio |
| `rename-*` | Rename Transcript |
| `speakers-*` | Speakers |
| `archive-*` | Library (inspector **Archive transcript** / **Include archived transcripts**) |
| `home` | Home |

Landing gallery (`website/images/`): same eight stills as the README **Screenshots**
section — `home.png`, `speaker-id.png` (from `speaker-identification-page.png`),
`corrections-studio.png`, `run-analysis.png` (from `first-analysis-run-analysis.png`),
`overview.png` (from `first-analysis-overview.png`), `transcript.png` (from
`speaker-identification-transcript.png`), `insights.png` (from
`investigate-highlights.png`), `charts-gallery.png`. Copy from
`docs/_static/workflows/` after recapture.

## Capture method

Product policy: do **not** add Playwright-driven Streamlit *acceptance* automation for docs media.

Practical approach used for the initial set:

1. Launch the web UI with a disposable data root (`TRANSCRIPTX_*_DIR`) and a written `schema_epoch.json` marker.
2. Import [`docs/workflows/fixtures/planning_review.json`](../workflows/fixtures/planning_review.json), name speakers, run **Balanced** analysis.
3. Select the transcript **and** run in the sidebar VIEW pickers before opening Overview / Insights / Artifacts.
4. Capture stills with Chromium (Playwright one-off helper [`scripts/docs_capture_workflow_media.py`](../../scripts/docs_capture_workflow_media.py) or OS screenshots).
5. Build short GIFs from a few stills (`ffmpeg` palette pipeline below, or `convert` + `gifsicle`) when a live interaction capture is awkward.
6. Keep raw files under `.local/workflow_media/`; promote curated assets to `docs/_static/workflows/`.

Do not couple production code to documentation capture.

**Launching against a disposable root:** export `TRANSCRIPTX_DATA_DIR`, `TRANSCRIPTX_OUTPUT_DIR`, `TRANSCRIPTX_TRANSCRIPTS_DIR`, `TRANSCRIPTX_CONFIG_DIR`, and `TRANSCRIPTX_RECORDINGS_DIR` before launching; exported keys win over the repo `.env`. Verify the Home counters show the fixture corpus (not your real library) before capturing anything, and keep the slug index (`outputs/.transcriptx_index.json`) free of container paths such as `/mnt/transcripts/…` if you reuse a root that was analysed in Docker — otherwise Library drops those rows.

**Landing on a page directly:** the app mirrors `page`, `subject_type`, `subject_id`, and `run_id` into the URL, and `?speaker_profile=<profile_id>` opens Speakers with that person selected. Use those deep links for stills that need a fresh session (full sidebar, no leftover state). Crop to the main panel when the sidebar is not part of the story (the November 2026 Groups / Rename / Corrections / Library stills are main-panel crops).

### Example compress commands

```bash
# PNG (lossy palette when text remains readable)
pngquant --quality=65-85 --ext .png --force docs/_static/workflows/*.png

# or lossless shrink
optipng -o2 docs/_static/workflows/*.png

# GIF from stills (ffmpeg; ~1.8 s per frame, 128-colour palette, 1100px wide)
printf "file 'frame_00.png'\nduration 1.8\nfile 'frame_01.png'\nduration 1.8\nfile 'frame_01.png'\n" > frames.txt
ffmpeg -f concat -safe 0 -i frames.txt \
  -vf "scale=1100:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer:bayer_scale=4" \
  -loop 0 out.gif

# GIF re-optimise (if gifsicle is installed)
gifsicle -O3 --colors 128 -o out.gif in.gif
```

If those tools are unavailable, use an equivalent compressor that keeps UI text legible.

## Asset checklist

Committed names expected by the walkthrough pages:

- `first-analysis-import.png`
- `first-analysis-run-analysis.png`
- `first-analysis-run-complete.gif`
- `first-analysis-overview.png`
- `speaker-identification-page.png` (legacy `speaker-trust-page.png`)
- `speaker-identification-naming.gif` (legacy `speaker-trust-naming.gif`)
- `speaker-identification-transcript.png` (legacy `speaker-trust-transcript.png`)
- `investigate-overview.png`
- `investigate-highlights.png`
- `investigate-evidence-jump.gif`
- `local-ai-llm-setup.png`
- `local-ai-overview-summary.png`
- `local-ai-meeting-extracts.png`
- `export-artifacts-browse.png`
- `export-panel.png`
- `export-download.gif`
- `export-html-preview.png`
- `charts-gallery.png`
- `home.png` (README / landing only)
- `corrections-studio.png`
- `corrections-correct-mode.png`
- `corrections-propose-panel.png`
- `groups-create-form.png`
- `groups-created.png`
- `groups-create.gif`
- `rename-form.png`
- `speakers-directory.png`
- `speakers-profile.png`
- `speakers-profile-identity.png`
- `archive-library-inspector.png`
- `archive-archived.png`
- `archive-include-archived.png`
- `archive-toggle.gif`

The November 2026 additions (Groups, Rename, Speakers, Corrections, Archive) were captured on the same BBNJ webinar corpus with six seeded longitudinal profiles; the group shown is `BBNJ webinar cohort`.

Embed images with GitHub-compatible Markdown so they render in the GitHub file view and in Sphinx/MyST:

```markdown
![Descriptive alt text](../_static/workflows/example.png)
```

Paths are relative to `docs/workflows/`. Alt text is required; captions are optional and only when they add information beyond surrounding prose.

The public landing hero is a copy of `first-analysis-overview.png` at [`website/images/overview.png`](../../website/images/overview.png). When you recapture Overview, copy it there as well.

## Rebuild docs

```bash
pip install -e '.[docs]'
make docs
# open docs/_build/html/workflows/index.html
```
