# Undiarized / single-speaker / partially-diarized resilience

Dense notes for loosening a hard diarization requirement in transcript analysis products, grounded in industry practice and TranscriptX’s current gates. Distinguishes **product policy** (default require human names) from **pipeline resilience** (skip honestly; do not crash).

---

## What do leading tools do with plain SRT/VTT/TXT with no speakers (Otter, Whisper without diarize, Zoom captions, YouTube auto-captions)?

### Takeaway
Consumer and caption pipelines treat undiarized text as first-class content for summaries and search, while speaker structure is either produced by a separate diarization step, pulled from meeting platforms, or left as generic “Speaker N / Unknown” until humans tag — they do not refuse the transcript.

### Cited Findings
- Otter imports audio/video and produces a transcript with AI summaries, action items, and outlines regardless of whether speakers are identified by voice enrollment; with speaker learning disabled, it still **separates turns via diarization** into Unknown / Speaker 1 / Speaker 2, and **Action Items, summaries, and Otter AI Chat are unaffected** by enrollment being off — [Otter: Disable Speaker Learning](https://help.otter.ai/hc/en-us/articles/40643231903639-Disable-Speaker-Learning); [Otter: Import audio/video](https://help.otter.ai/hc/en-us/articles/360047733574-Import-an-audio-or-video-file).
- Otter Dropbox sync initially writes a transcript **without speaker names**, then updates the file after speaker identification finishes — [Otter: Dropbox for Otter](https://help.otter.ai/hc/en-us/articles/360048070254-Dropbox-for-Otter).
- Fireflies exposes per-sentence `speaker_name` / `speaker_id` and meeting-level analytics (including per-speaker duration/word counts) plus summary fields that are content-oriented; speaker names can be edited post-hoc (apply to all / current) — [Fireflies transcript query](https://docs.fireflies.ai/graphql-api/query/transcript); [Fireflies: edit speaker labels](https://guide.fireflies.ai/hc/en-us/articles/360020248198-How-to-edit-speaker-labels-or-names-in-a-transcript).
- Plain Whisper does **not** label speakers; undiarized turns render as Unassigned until humans or a diarizer assign them; Potato’s converter reports Whisper JSON as `undiarized` vs WhisperX as `N speaker(s)` — [Potato: Annotate Whisper transcripts](https://www.potatoannotator.com/docs/guides/annotating-whisper-transcripts).
- WhisperX diarization is an **opt-in** `--diarize` flag (HF token + pyannote model acceptance); without it, output is timed ASR without speaker IDs — [WhisperX README](https://github.com/m-bain/whisperX/); TranscriptX recipe documents the same: run without `--diarize` if you prefer not to use diarization — [docs/recipes/whisperx/README.md](/Users/89298/Documents/transcriptx/docs/recipes/whisperx/README.md).
- AssemblyAI `speaker_labels` defaults to **false**; enabling it returns utterances with speaker IDs; multi-channel audio is the preferred path when channels are already separated — [AssemblyAI: Speaker Diarization](https://www.assemblyai.com/docs/pre-recorded-audio/label-speakers); [AssemblyAI FAQ: Speaker Labels vs Multi-channel](https://www.assemblyai.com/docs/faq/should-i-use-speaker-labels-or-multi-channel).
- YouTube **auto-captions never include speaker labels**; multi-speaker speech exports as one continuous unattributed stream in SRT/VTT — [Potato: Annotate YouTube subtitles](https://www.potatoannotator.com/docs/guides/annotating-youtube-subtitles); [YouTubeScribe: auto captions](https://youtubescribe.com/blog/caption-endpoint).
- Zoom: cloud **audio transcript** VTT can include participant names; live/local **closed-caption** exports often do **not**; Zoom staff stated CC service does not include speaker names while the audio transcript does — [Zoom Dev Forum](https://devforum.zoom.us/t/how-can-i-get-transcript-closed-caption-with-speaker-name/95778); [IT@Cornell transcription overview](https://it.cornell.edu/video-accessibility-captioning/transcription-caption-overview).

### Inferences
- Industry default is **content-first, speakers-optional**: undiarized or anonymously diarized transcripts still get summaries, search, and export.
- “No speakers” in the wild usually means one of three states, not one: (1) pure caption stream (YouTube auto, many SRT/VTT), (2) diarized-but-unnamed (Speaker 1 / SPEAKER_00), (3) platform-named without voice ID (Zoom cloud transcript).
- Tools that care about speakers still **admit** undiarized files and surface assignment UX rather than blocking ingest.

### Gaps
- No primary Otter/Fireflies docs found that describe importing a raw undiarized `.srt`/`.txt` (without re-transcription) as a first-class path; their documented import paths are audio/video → ASR with their own diarization.
- Descript’s exact undiarized-import product behavior was not verified from a primary Descript help article in this pass (Potato’s “Unassigned” pattern is annotation tooling, not Descript itself).

---

## Academic/product patterns: require diarization vs degrade gracefully; min_named_speakers gating; allow_unnamed_speakers; treat whole file as one speaker

### Takeaway
Mature products separate **diarization** (partition turns) from **identification** (human names), default to honest degradation (skip or generic labels), and use speaker-count gates for interaction modules — TranscriptX already implements named-vs-unnamed gating with an explicit ungate, but does not yet synthesize a monologue persona for fully speakerless files.

### Cited Findings
- Otter explicitly separates **diarization** (Speaker 1/2 bubbles) from **enrollment/identification** (voice data → person); summaries still run when enrollment is off — [Otter: Disable Speaker Learning](https://help.otter.ai/hc/en-us/articles/40643231903639-Disable-Speaker-Learning).
- AssemblyAI treats speaker labels as optional; when enabled, `speakers_expected` / `min_speakers_expected` / `max_speakers_expected` are **hard bounds** (wrong exact count can merge or over-split) — [AssemblyAI: Speaker Diarization](https://www.assemblyai.com/docs/pre-recorded-audio/label-speakers).
- WhisperX assigns anonymous `SPEAKER_00`… only when `--diarize` runs; `assign_word_speakers` can leave segments without speakers or fill nearest; diarization “is far from perfect” per project limitations — [WhisperX README](https://github.com/m-bain/whisperX/); [whisperx/diarize.py assign_word_speakers](https://github.com/m-bain/whisperX/blob/main/whisperx/diarize.py).
- Potato / research annotation: for single-speaker audio, “diarization is unnecessary: assign all turns to one speaker”; undiarized Whisper → Unassigned with picker — [Potato: Annotate Whisper transcripts](https://www.potatoannotator.com/docs/guides/annotating-whisper-transcripts).
- TranscriptX **product policy**: named speakers required by default; `analysis.allow_unnamed_speakers` (global) **or** Run Analysis checkbox (per-run) ungates so diarized labels count — [docs/runtime/settings.md](/Users/89298/Documents/transcriptx/docs/runtime/settings.md); [CHANGELOG unnamed-speaker ungate](/Users/89298/Documents/transcriptx/CHANGELOG.md).
- TranscriptX gate math: `effective_min_named_speakers = max(min_named_speakers, 2 if requires_multiple_speakers else 1)`; default `min_named_speakers=1` — [module_registry.py](/Users/89298/Documents/transcriptx/src/transcriptx/core/pipeline/module_registry.py).
- When ungated, skip reason uses **turn-taking** speaker count (`SPEAKER_00` counts); when gated, uses **named** count — [dag_pipeline_run.py `speaker_gate_skip_reason`](/Users/89298/Documents/transcriptx/src/transcriptx/core/pipeline/dag_pipeline_run.py); [text_utils.py `is_named_speaker` / `is_turn_taking_speaker_label`](/Users/89298/Documents/transcriptx/src/transcriptx/utils/text_utils.py).
- Multi-speaker modules flag `requires_multiple_speakers: True` (e.g. conversation_loops, contagion, interactions, echoes, semantic_similarity, Q&A pairs) — [module_specs/conversation.py](/Users/89298/Documents/transcriptx/src/transcriptx/core/pipeline/module_specs/conversation.py); [module_specs/qa.py](/Users/89298/Documents/transcriptx/src/transcriptx/core/pipeline/module_specs/qa.py); [module_specs/topics.py](/Users/89298/Documents/transcriptx/src/transcriptx/core/pipeline/module_specs/topics.py).
- Charts overview honesty: on monologues (one named speaker), multi-speaker overview slots are filtered out — [docs/workflows/charts.md](/Users/89298/Documents/transcriptx/docs/workflows/charts.md); [chart_registry.py `filter_overview_viz_ids_for_named_speakers`](/Users/89298/Documents/transcriptx/src/transcriptx/core/utils/chart_registry.py).
- TranscriptX speaker-map CLI path **refuses** creating a map when all segments have `speaker: None` and tells the user to run diarization first — [speaker_mapping/core.py](/Users/89298/Documents/transcriptx/src/transcriptx/io/speaker_mapping/core.py).
- SRT/VTT import preserves optional `speaker_hint` (e.g. `Name: text` prefix) but does **not** invent a synthetic speaker when hints are absent — [srt_engine.py](/Users/89298/Documents/transcriptx/src/transcriptx/io/import_adapters/subtitle/srt_engine.py); [srt_parser.py `_extract_speaker_hint`](/Users/89298/Documents/transcriptx/src/transcriptx/io/srt_parser.py).
- Capability detection: `has_speaker_labels = any("speaker" in seg for seg in segments)` (key presence, not namedness) — [canonical_transcript.py](/Users/89298/Documents/transcriptx/src/transcriptx/core/domain/canonical_transcript.py). Many modules list `Requirement.SPEAKER_LABELS` — [module_requirements.py](/Users/89298/Documents/transcriptx/src/transcriptx/core/domain/module_requirements.py).
- Output contract: unidentified speakers excluded from per-speaker charts by default; transcript/CSV/NER may still include them; eligibility via `is_named_speaker` — [docs/contracts/output-contract-v1.md](/Users/89298/Documents/transcriptx/docs/contracts/output-contract-v1.md).

### Inferences
- Best product pattern: **three layers** — (A) admit any timed text, (B) optional diarization → anonymous IDs, (C) optional naming → human identities — with modules declaring which layer they need.
- `allow_unnamed_speakers` is the right lever for (B)→analysis without (C); it does **not** invent (B) from undiarized (A).
- Treating the whole file as one speaker is a common research/annotation pattern for true monologues; TranscriptX softens multi-speaker charts for one **named** speaker but does not auto-mint a monologue ID for speakerless SRT/VTT.

### Gaps
- No TranscriptX code path found that auto-assigns a synthetic `SPEAKER_00` / “Narrator” when importing speakerless SRT/VTT/TXT (gap between industry monologue practice and current import).
- Academic paper citations on “graceful degradation of conversational NLP without diarization” were not collected in this pass; patterns above are product/engineering primary sources.

---

## When is post-hoc diarization (pyannote on audio + forced alignment) preferred vs accepting undiarized text?

### Takeaway
Prefer post-hoc diarization when audio exists and the analysis goal needs turn structure (who-said-what, interactions, Q&A); accept undiarized text when audio is missing, cost/latency dominates, or only content modules matter — and never silently invent speakers without audio evidence.

### Cited Findings
- pyannote’s documented merge path: run diarization (prefer **exclusive** mode so one speaker is active per interval) and ASR independently, then align by timestamp overlap (WhisperX-style `assign_word_speakers`); segments with no overlap can get `UNKNOWN` or nearest fill — [pyannoteAI: merge diarization and STT](https://docs.pyannote.ai/tutorials/diarization-asr-merge); [pyannote community-1 exclusive mode](https://www.pyannote.ai/blog/community-1).
- Word-level alignment is preferred over snapping whole ASR segments because segments often straddle speaker changes; exclusive diarization simplifies STT merge for overlapped speech — [pyannote: subtitles with speaker labels](https://www.pyannote.ai/blog/subtitles-with-speaker-labels-pyannoteai-asr).
- WhisperX packages ASR → wav2vec2 alignment → optional pyannote diarize → `assign_word_speakers`; without `--diarize`, you keep timed text only — [WhisperX README](https://github.com/m-bain/whisperX/).
- YouTube auto-caption streams have **no recoverable speaker marker**; “any tool that claims to add speaker labels to an automatic YouTube track is running its own diarisation over something” (needs audio) — [YouTubeScribe](https://youtubescribe.com/blog/caption-endpoint).
- AssemblyAI: each speaker should have ~30s continuous speech for good clustering; overlapping speech and short backchannels hurt accuracy — [AssemblyAI: Speaker Diarization best practices](https://www.assemblyai.com/docs/pre-recorded-audio/label-speakers).
- TranscriptX Theme **H** ships host-orchestrated Whisper-class STT with optional WhisperX Docker diarization (`HF_TOKEN`, `--diarize`); BYO import remains default; analysis image does not embed STT — [docs/ROADMAP.md theme H](/Users/89298/Documents/transcriptx/docs/ROADMAP.md); [docs/runtime/transcription.md](/Users/89298/Documents/transcriptx/docs/runtime/transcription.md).
- Backlog **B19** (diarization / speaker-map consistency diagnostics) is planned to get richer when Theme H word/diarization provenance exists — [docs/dev/analysis_module_backlog_2026-07-17.md](/Users/89298/Documents/transcriptx/docs/dev/analysis_module_backlog_2026-07-17.md).

### Inferences
- **Prefer post-hoc diarization when:** (1) source audio (or multichannel) is available, (2) user wants interaction / per-speaker / Q&A modules, (3) caption-only import would otherwise leave `speaker: None` and block speaker-id UX, (4) re-transcribing is acceptable cost.
- **Accept undiarized text when:** (1) no audio, (2) monologue / lecture / voice-note where one synthetic speaker is enough, (3) only topics/sentiment/readability/global LLM summary are needed, (4) diarization quality would be worse than honesty (noisy overlap, very short speakers).
- For TranscriptX specifically: WhisperX `--diarize` at STT time is the supported path to anonymous speakers; post-hoc pyannote-on-existing-JSON is not a first-class product surface yet (import + optional re-STT).

### Gaps
- No measured DER/WER tradeoff numbers collected for “re-STT with diarize vs pyannote-on-existing Whisper JSON” in this pass.
- TranscriptX does not currently expose a one-click “diarize this library transcript’s audio” repair; only full STT recipes / Theme H jobs.

---

## Implications for inherently multi-speaker modules vs content modules

### Takeaway
Multi-speaker modules must stay gated (or explicitly ungated on anonymous IDs); content modules should run on undiarized or synthetic-single-speaker text with clear UI that per-speaker views are N/A — mixing the two without honesty produces empty charts that look like bugs.

### Cited Findings
- TranscriptX multi-speaker-required modules include conversation_loops, contagion, interactions, echoes, semantic_similarity, and Q&A (among others) via `requires_multiple_speakers: True` — [conversation.py](/Users/89298/Documents/transcriptx/src/transcriptx/core/pipeline/module_specs/conversation.py); [topics.py](/Users/89298/Documents/transcriptx/src/transcriptx/core/pipeline/module_specs/topics.py); [qa.py](/Users/89298/Documents/transcriptx/src/transcriptx/core/pipeline/module_specs/qa.py).
- Content-leaning modules (topic_modeling, bertopic, wordclouds) do **not** set `requires_multiple_speakers` but still declare `SPEAKER_LABELS` in many registry entries / default requirements — [topics.py](/Users/89298/Documents/transcriptx/src/transcriptx/core/pipeline/module_specs/topics.py); [nlp.py](/Users/89298/Documents/transcriptx/src/transcriptx/core/pipeline/module_specs/nlp.py).
- Default named-speaker gate skips modules with “requires at least N named speakers”; overnight helper can run `transcript_output,llm_summary` with `--allow-unnamed-speakers` — [docs/runtime/overnight-host.md](/Users/89298/Documents/transcriptx/docs/runtime/overnight-host.md); [settings.md](/Users/89298/Documents/transcriptx/docs/runtime/settings.md).
- Echoes/contagion were fixed to use turn-taking labels / raw diarization IDs when ungated so charts render on diarized-but-unnamed transcripts — [CHANGELOG.md](/Users/89298/Documents/transcriptx/CHANGELOG.md).
- Otter: speaker enrollment off does **not** disable Action Items / summaries / AI Chat — [Otter Disable Speaker Learning](https://help.otter.ai/hc/en-us/articles/40643231903639-Disable-Speaker-Learning).
- Fireflies analytics include both global categories (questions, tasks) and per-speaker analytics — structure allows content insights without perfect names — [Fireflies transcript schema](https://docs.fireflies.ai/schema/transcript).
- UX honesty already used in TranscriptX Charts: sparse charts → check Overview for skipped modules; monologue overview omits multi-speaker slots — [docs/workflows/charts.md](/Users/89298/Documents/transcriptx/docs/workflows/charts.md).

### Inferences
- **Hard multi-speaker** (turn-taking, contagion, Q&A pairs, echoes, interaction networks): need ≥2 distinct turn-taking labels; without diarization, skip with reason; with one synthetic speaker, skip — do not invent fake turns.
- **Soft multi-speaker / per-speaker content** (per-speaker sentiment, llm_speaker_summary): need ≥1 eligible speaker (named by default; unnamed if ungated); empty speaker field → skip or bucket as whole-transcript only.
- **Content / global** (topics, readability, global sentiment, llm_summary, transcript_quality): should tolerate undiarized text; if registry still lists `SPEAKER_LABELS`, that is an engineering coupling to loosen, not a scientific requirement.
- UX honesty pattern: surface capability tier on Overview (“undiarized — interaction modules skipped”) rather than empty galleries.

### Gaps
- Exact list of which modules still fail `SPEAKER_LABELS` when the `speaker` key is absent (vs present-but-None) was not exhaustively tested here; capability check only looks for key presence.
- No industry matrix documenting which Gong/Chorus-class modules refuse undiarized imports (comparison docs point to vendor pages; not re-fetched).

---

## Recommended capability matrix: undiarized → single synthetic speaker → diarized unnamed → named speakers

### Takeaway
A four-tier capability model matches both industry practice and TranscriptX’s existing knobs: keep **named required by default** (product policy), make tiers **explicit in planning/skip reasons** (pipeline resilience), and only auto-promote undiarized→synthetic when the user opts into monologue mode or audio proves one cluster.

### Cited Findings
- Industry ladder observed: caption-only (YouTube) → optional diarize anonymous (WhisperX/AssemblyAI) → platform or manual names (Zoom/Otter/Fireflies) → voice enrollment (Otter) — sources in sections above.
- TranscriptX today effectively implements tiers **diarized unnamed** (ungate) and **named** (default); monologue overview filtering exists for one named speaker; undiarized and synthetic-single are incomplete — [settings.md](/Users/89298/Documents/transcriptx/docs/runtime/settings.md); [charts.md](/Users/89298/Documents/transcriptx/docs/workflows/charts.md); [speaker_mapping/core.py](/Users/89298/Documents/transcriptx/src/transcriptx/io/speaker_mapping/core.py).
- Theme H keeps STT optional and outside the analysis image; diarization via WhisperX is operator-chosen — [ROADMAP.md H](/Users/89298/Documents/transcriptx/docs/ROADMAP.md); [transcription.md](/Users/89298/Documents/transcriptx/docs/runtime/transcription.md).

### Inferences — recommended matrix (grounded in TranscriptX)

| Tier | Signal | What runs | What skips / honesty | TranscriptX today |
|------|--------|-----------|----------------------|-------------------|
| **T0 Undiarized** | No speaker field / all None; timed or plain text | Global content: topics, wordclouds, readability, global sentiment, `llm_summary`, transcript_quality, exports | All interaction / per-speaker; Overview banner: “No speaker labels” | Import SRT/VTT OK; analysis mostly blocked by named-speaker gate + SPEAKER_LABELS; speaker-map CLI refuses |
| **T1 Single synthetic speaker** | Operator or policy assigns one ID (e.g. `SPEAKER_00` / display name) to all turns | Everything that needs ≥1 speaker; per-speaker artifacts are whole-file | Modules with `requires_multiple_speakers` | Not auto-created on import; achievable manually if user labels one speaker |
| **T2 Diarized unnamed** | `SPEAKER_00`… / Speaker N; `allow_unnamed_speakers` | Interaction + per-speaker under anonymous IDs | Named-only UX (profiles, longitudinal) may stay limited | **Shipped** via global/per-run ungate |
| **T3 Named speakers** | Human display names via Speaker ID | Full Balanced/Thorough; profiles; llm_speaker_summary | None for speaker reasons | **Default product policy** |

**Policy vs resilience (recommended stance for TranscriptX):**
- **Product policy (keep):** default require T3 for “meaningful” Balanced runs; prompt Speaker Identification.
- **Pipeline resilience (strengthen):** never crash on T0; skip with stable reasons; optionally offer “Treat as single speaker” → T1; optionally offer “Re-transcribe with diarize” / Theme H → T2; keep `allow_unnamed_speakers` for T2 without naming.
- **Target-speaker mode** (future): filter analysis to one named/diarized ID (interview focus) — distinct from monologue; not shipped as a first-class flag today.
- **Post-hoc diarization:** prefer when climbing T0→T2 with audio present; do not invent T2 without audio.

### Gaps
- No committed TranscriptX design doc yet specifies T0/T1 product UX (“Treat as single speaker” checkbox); recommendation above is inferred from settings + industry, not an existing RFC.
- Target-speaker analysis mode is suggested by interview workflows but not found as a named feature in current settings.

---

## TranscriptX current gates: what already softens vs what still hard-requires speakers

### Takeaway
TranscriptX has already loosened **named** requirements via `allow_unnamed_speakers` and multi-speaker chart honesty, but still **hard-requires some form of speaker field** for most modules and does not gracefully run a content-only path on speakerless SRT/VTT without operator workarounds.

### Cited Findings — already softens
- Default named gate + explicit ungate (global OR per-run) — [settings.md](/Users/89298/Documents/transcriptx/docs/runtime/settings.md); [speaker_ungate.py](/Users/89298/Documents/transcriptx/src/transcriptx/core/pipeline/speaker_ungate.py); [pipeline_context.py](/Users/89298/Documents/transcriptx/src/transcriptx/core/pipeline/pipeline_context.py).
- `is_turn_taking_speaker_label` vs `is_named_speaker` for interaction eligibility when ungated — [text_utils.py](/Users/89298/Documents/transcriptx/src/transcriptx/utils/text_utils.py).
- `min_named_speakers` / `requires_multiple_speakers` registry fields; `speaker_gate_skip_reason` returns skip strings instead of crashing — [module_registry.py](/Users/89298/Documents/transcriptx/src/transcriptx/core/pipeline/module_registry.py); [dag_pipeline_run.py](/Users/89298/Documents/transcriptx/src/transcriptx/core/pipeline/dag_pipeline_run.py).
- Monologue overview chart filtering — [chart_registry.py](/Users/89298/Documents/transcriptx/src/transcriptx/core/utils/chart_registry.py).
- WhisperX import promotes word-level speakers to segment level when segment speaker missing; warns if still missing — [whisperx_engine.py](/Users/89298/Documents/transcriptx/src/transcriptx/io/import_adapters/json_vendor/whisperx_engine.py).
- Zoom VTT adapter extracts speaker hints from cue text when present — [zoom_engine.py](/Users/89298/Documents/transcriptx/src/transcriptx/io/import_adapters/subtitle/zoom_engine.py).
- Docs + overnight path acknowledge unnamed analysis for limited module sets — [overnight-host.md](/Users/89298/Documents/transcriptx/docs/runtime/overnight-host.md); [transcription.md](/Users/89298/Documents/transcriptx/docs/runtime/transcription.md).
- Theme H / WhisperX recipe: diarization optional (`--diarize` + `HF_TOKEN`) — [whisperx README recipe](/Users/89298/Documents/transcriptx/docs/recipes/whisperx/README.md).

### Cited Findings — still hard-requires / sharp edges
- Speaker Identification / speaker-map creation aborts when no speaker IDs exist — [speaker_mapping/core.py](/Users/89298/Documents/transcriptx/src/transcriptx/io/speaker_mapping/core.py).
- Most module specs list `Requirement.SPEAKER_LABELS` — undiarized segments without a `speaker` key fail capability checks — [module_requirements.py](/Users/89298/Documents/transcriptx/src/transcriptx/core/domain/module_requirements.py); [canonical_transcript.py](/Users/89298/Documents/transcriptx/src/transcriptx/core/domain/canonical_transcript.py).
- SRT/VTT adapters pass through `speaker_hint` only; no synthetic monologue speaker — [srt_engine.py](/Users/89298/Documents/transcriptx/src/transcriptx/io/import_adapters/subtitle/srt_engine.py); [vtt_engine.py](/Users/89298/Documents/transcriptx/src/transcriptx/io/import_adapters/subtitle/vtt_engine.py).
- Product copy still says most Balanced modules skip until speakers are **named** — [transcription.md](/Users/89298/Documents/transcriptx/docs/runtime/transcription.md); [README.md](/Users/89298/Documents/transcriptx/README.md).
- `allow_unnamed_speakers` does not help pure undiarized files (zero turn-taking labels) — gate still sees count 0 — [dag_pipeline_run.py](/Users/89298/Documents/transcriptx/src/transcriptx/core/pipeline/dag_pipeline_run.py).

### Inferences
- Softening already done: **T2↔T3** (unnamed ungate) and **multi vs single named** chart honesty.
- Remaining hard edge for the research objective: **T0** (and optional **T1** minting) so YouTube/Zoom-caption/Whisper-without-diarize imports get a content-only or monologue path without pretending to have conversation structure.
- Distinguishing policy from resilience: keep default “name speakers” UX; change resilience so undiarized imports **skip interaction modules with clear reasons** and still deliver content/export modules.

### Gaps
- End-to-end behavior of importing a speakerless YouTube VTT then running Balanced (exact skip set) was not executed in this research pass — inferred from gates/code.
- Whether admission normalizes missing `speaker` keys away (affecting `has_speaker_labels`) vs writing `"speaker": null` was not fully traced through the managed import serializer.
