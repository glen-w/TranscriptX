# How TranscriptX compares — reference

Vendor-by-vendor notes and the longer capability tables. Most readers only need [How TranscriptX compares](comparison.md).

**Last reviewed:** 2026-09-02. Feature lists for other products are based on public docs and positioning — not paid pilots.

## Capability snapshot

Legend: **Yes** = first-class · **Partial** = adjacent or lighter · **No** = absent or out of scope · **N/A** = not that product’s job.

| Capability | TranscriptX | Scriberr | Nanosamurai | RiverScript | Otter / Fireflies | Gong / Chorus / Avoma | CallMiner-class |
|------------|-------------|----------|-------------|-------------|-------------------|------------------------|-----------------|
| Local / air-gapped analysis | Yes | Yes (local mode) | Partial (self-hosted STT; NVIDIA GPU; not turnkey air-gap) | No (hosted SaaS; on-device VAD only) | No | No | No |
| Built-in speech-to-text | No (BYO) | Yes | Yes (live + refine + final) | Yes | Yes | Yes (via capture) | Partial |
| Meeting bot / auto-join | No | No | No | No (system-audio capture instead) | Yes | Yes | Partial |
| Language, speakers, and interaction analysis | Yes | No | No | No | Partial | Partial–Yes | Yes (CC domain) |
| Emotion / interaction / voice stacks | Yes | No | Partial (enrollment / diarization) | No | Partial | Partial | Yes (domain) |
| Multi-session groups + charts | Yes | No | No | No | Partial | Partial (deal/team) | Yes (agent/team) |
| Saved analysis files you can reopen or script | Yes | Partial (API) | Partial (OpenAPI / SDK / protobuf) | Partial (public API / MCP for shares) | No | No | No |
| CRM / revenue pipeline | No | No | No | No | Partial | Yes | Partial |
| Chat / Ask-AI over meetings | No (by design) | Yes | No | Yes | Yes | Yes | Partial |
| Local LLM (Ollama) | Yes | Yes | No | No | No | No | No |

Qualitative-research cluster (noScribe, CAQDAS, DoReveal / Dovetail, Oral History as Data): [table below](#qualitative-research-coding-and-oral-history).

## Complementary: transcription upstreams

### Scriberr

- **Sites:** [scriberr.app](https://scriberr.app/) · [GitHub](https://github.com/rishikanthc/Scriberr)
- **Fit:** Offline-friendly self-hosted transcription workspace — local models (e.g. Parakeet / Canary / Whisper-class), diarization, polished transcript reader, notes, folder watch / API, optional Ollama or OpenAI-compatible chat.
- **With TranscriptX:** Use Scriberr to **create** transcripts; use TranscriptX to **analyse** a corpus over time.
- **Not a substitute for:** TranscriptX’s module DAG, group analytics, or contract-backed research outputs.

### noScribe

- **Sites:** [noscribe.de](https://noscribe.de/en/) · [GitHub](https://github.com/kaixxx/noScribe)
- **Fit:** GPL-3.0 **desktop interview transcriber** (Windows, macOS, Linux) aimed at qualitative social research and other sensitive audio. Runs **entirely locally** (faster-whisper + pyannote); no cloud. Speaker distinction, ~60 languages, pauses / overlap / timestamps, optional filler-word handling, and a dedicated editor to correct against the audio. Default export is **HTML** (opens in Word / LibreOffice and common QDA packages); also **plain text** and **WebVTT** (often used as a bridge into [EXMARaLDA](https://exmaralda.org/)). The author warns that **noscribe.ai** is an unrelated paid service.
- **With TranscriptX:** Use noScribe to **create** a reviewed interview transcript; import **VTT** (preferred) or HTML/TXT into TranscriptX to **analyse** a corpus computationally.
- **Not a substitute for:** TranscriptX’s analysis modules, groups, charts, or contracts. noScribe is local STT + a correction editor, not conversational science. It is also not a Jeffersonian CA transcriber (see [EMCA resources](#conversation-analysis--emca-resources) below).

### aTrain

- **Sites:** [GitHub](https://github.com/aTrainTranscription/aTrain) · [BANDAS / University of Graz](https://business-analytics.uni-graz.at/en/research/atrain/)
- **Fit:** AGPL-3.0 **offline interview transcriber** (GUI + CLI) from researchers at the University of Graz. faster-whisper + pyannote speaker detection; recordings never leave the device (GDPR-oriented). Packaged on **Flathub** (Linux) and the **Microsoft Store** (Windows); NVIDIA CUDA optional for speed; macOS installers still on their roadmap (CPU via pip is possible). ~99 languages. Exports **plain TXT** (with/without timestamps and speakers), a **QDA-formatted TXT** for [MAXQDA](https://www.maxqda.com/) / [ATLAS.ti](https://atlasti.com/) / [NVivo](https://lumivero.com/products/nvivo/) (click timestamp → play audio), and a **JSON** dump of the raw transcript. Headless: `aTrain_core transcribe`. Compared with noScribe: aTrain emphasises QDA import + CUDA speed; noScribe emphasises a dedicated correction editor and VTT/HTML.
- **With TranscriptX:** Use aTrain to **create** an interview transcript; import **TXT** (or JSON if segments have `start` / `end` / `speaker` / `text`). Then analyse locally in TranscriptX, and/or continue coding in CAQDAS.
- **Not a substitute for:** TranscriptX’s analysis modules, groups, charts, or contracts. aTrain is local STT + QDA-oriented export, not conversational science.

### Amical

- **Sites:** [amical.ai](https://amical.ai/) · [docs](https://amical.ai/docs) · [GitHub](https://github.com/amicalhq/amical)
- **Fit:** MIT-licensed **local-first dictation app** for macOS and Windows (Electron). Push-to-talk / hands-free: speech lands in the focused app, with optional local Whisper + Ollama or cloud STT, custom vocabulary, and context-aware formatting. Meeting transcription (mic + system audio) is a product direction, not the core job. A 2025 roundup on their blog ([open-source transcription software](https://amical.ai/blog/open-source-transcription-software)) also lists engines (Whisper, Vosk, Kaldi, DeepSpeech, WhisperX) — those are libraries, not analysis workbenches.
- **With TranscriptX:** Amical is **dictation**, not a corpus transcriber. If you save notes or paste a transcript as **TXT**, you can import that text; there is no first-class timed JSON/SRT handoff comparable to WhisperX or noScribe VTT.
- **Not a substitute for:** TranscriptX’s analysis modules, or for interview/file STT tools such as noScribe, aTrain, Scriberr, or WhisperX.

### Nanosamurai

- **Sites:** [nanosamur.ai](https://nanosamur.ai) · [GitHub](https://github.com/nanosamurai/nanosamurai)
- **Fit:** Apache-2.0 **org-grade speech platform** — browser UI + Windows Electron app, realtime captions with replaceable partials, asynchronous WhisperX refinement, canonical final transcripts with word timings and karaoke playback, speaker enrollment / diarization, PostgreSQL + object storage, Python SDK/CLI, optional Grafana/Tempo/Loki. Aimed at organisations that cannot send audio to a third party (on-prem / private cloud). Community Edition is a Docker Compose evaluator; default speech path expects an **NVIDIA GPU**. Agentic workflows and webhooks are public contracts, not shipped runners.
- **With TranscriptX:** Use Nanosamurai to **capture and transcribe** sensitive sessions on infrastructure you control; export the **final** transcript (and recording) and import into TranscriptX to **analyse** a corpus. Personal / laptop-first STT is usually simpler with Scriberr or WhisperX.
- **Not a substitute for:** TranscriptX’s analysis modules, groups, charts, or file-backed research contracts. Nanosamurai is capture + STT + session records, not conversational science.

### RiverScript

- **Sites:** [riverscript.com](https://riverscript.com/) · [product docs](https://riverscript.com/docs/introduction/what-is-riverscript) · [founder notes](https://lexvalo.com/riverscript)
- **Fit:** Hosted AI transcription **workspace** (web app + Tauri desktop for Windows and macOS). Three ingest paths: upload audio/video (publicly claimed up to **50 GB** / **8 hours**), in-app microphone recording, and **Live Recording Transcription** of system audio (WASAPI on Windows, ScreenCaptureKit on macOS) — webinars, calls, streams, any app — without a Zoom/Meet bot. Desktop runs **on-device Silero VAD** (ONNX) so silence is stripped before audio is sent. STT is multi-provider with fallback (self-hosted Whisper v3, Deepgram Nova, ElevenLabs Scribe). Built-in editor + player, speaker diarization, translation (~100 languages), AI Summarize & Ask, share links, public API and [MCP](https://github.com/lexvalo/riverscript-mcp) for shared transcripts. Timed exports are **SRT / VTT**; untimed **TXT / DOCX / PDF**. Operator infrastructure is in Helsinki; audio retained **7 days**, transcripts until you delete them.
- **With TranscriptX:** Use RiverScript to **capture and transcribe** (especially live system audio and large media); export **SRT/VTT** (or TXT) and import into TranscriptX to **analyse** a corpus locally.
- **Not a substitute for:** TranscriptX’s module DAG, group analytics, local-first retention, or contract-backed research outputs. RiverScript is capture + STT + notes/chat, not conversational science. It is also **not** a self-hosted or air-gapped STT path (unlike Scriberr / noScribe / aTrain / Nanosamurai).

### Other STT / subtitle paths

**Apps and recipes we already document:** WhisperX, Whisper-WebUI (SRT/VTT), AssemblyAI, Deepgram, Otter exports, RiverScript SRT/VTT, noScribe VTT/HTML/TXT, aTrain TXT/JSON, and manual JSON. Recipes: [WhisperX](recipes/whisperx/README.md), [Whisper-WebUI](recipes/whisper-webui/README.md).

**Engines and toolkits** (not TranscriptX substitutes; produce text or subtitles you can import):

- **OpenAI Whisper** (and ports such as whisper.cpp / faster-whisper) — the model behind whispermlx, WhisperX, noScribe, aTrain, Scriberr, and Amical’s local path.
- **[WhisperX](https://github.com/m-bain/whisperX)** — Whisper plus word-level alignment and optional pyannote diarization; our usual JSON import example.
- **[Vosk](https://alphacephei.com/vosk/)** — lightweight offline ASR (small models, streaming API, embedded/Raspberry Pi). Weaker than Whisper-class models on noisy/multi-speaker audio; a library, not a workbench.
- **[Kaldi](https://kaldi-asr.org/)** — research ASR toolkit (recipes, custom training). Steep CLI/Linux curve; no GUI.
- **Mozilla DeepSpeech** — historically common; **official development stopped**. Prefer Whisper-class or Vosk for new local STT work.

## Meeting assistants (SaaS)

**Otter.ai**, **Fireflies.ai**, and similar products excel at **capture + same-day notes**: bots that join calls, live or near-live transcripts, searchable org libraries, and light “Ask AI” over meetings.

**[RiverScript](https://riverscript.com/)** is adjacent rather than the same product: it captures meeting and webinar audio via **desktop system recording** (no calendar bot), then offers an editor, timed subtitles, translation, and Summarize & Ask. Team auto-join, org libraries, and CRM-style meeting ops remain Otter / Fireflies / Avoma territory.

**Choose Otter / Fireflies / Avoma when** team rollout and automatic recording matter more than local control or deep conversational science. **Choose RiverScript when** you want bot-free desktop capture of whatever is playing on the machine, large-file transcription, and a hosted editor — then import into TranscriptX if you need local analysis.

**Choose TranscriptX when** recordings or transcripts already exist (or come from a local or hosted STT tool), privacy / local retention matters, and you want structured multi-module analysis and exports you keep.

## Revenue & coaching conversation intelligence (SaaS)

**Gong**, **Chorus by ZoomInfo**, and **Avoma** productise **sales conversation intelligence**: talk patterns, trackers (objections, competitors, themes), scorecards, coaching, and CRM / pipeline hooks.

**CallMiner** (and adjacent tools such as Observe.ai) do analogous work for **contact centers**: scorecards, sequencing, omnichannel coverage, agent coaching.

**Choose them when** deal or agent outcomes tied to CRM/CCaaS are the product.

**Choose TranscriptX when** you want general conversational analytics without a sales or contact-center SaaS stack — still local, modular, and file-backed.

These vendors set a useful **UX bar** for trackers, talk ratios, and longitudinal views. TranscriptX does not aim to clone their capture/CRM platforms.

## Qualitative research, coding, and oral history

TranscriptX’s **emerging** audience includes researchers who want trustworthy structured outputs ([PRODUCT.md](PRODUCT.md)). That is not the same job as **CAQDAS** (you apply codes and memos), **AI qualitative synthesis** (a hosted team produces themes, grids, and reports), **conversation-analytic transcription** (Jefferson / GAT / Mondada on a timeline), or **digital exhibits** of coded oral histories.

Legend as above.

| Capability | TranscriptX | noScribe | CAQDAS (NVivo / MAXQDA / ATLAS.ti / Quirkos) | DoReveal / Dovetail | Oral History as Data |
|------------|-------------|----------|-----------------------------------------------|---------------------|----------------------|
| Local / air-gapped analysis | Yes | Yes (STT + editor) | Partial (desktop apps; some cloud collab) | No | Yes (static site you host) |
| Built-in speech-to-text | No (BYO) | Yes | Partial | Yes | No |
| Researcher coding / codebook / memos | No | No | Yes | Partial–Yes (tags + AI) | Partial (CSV tags) |
| Automatic analysis of language and interaction | Yes | No | No | Partial (AI themes) | No |
| Emotion / interaction / voice stacks | Yes | No | No | Partial (DoReveal: emotion in synthesis) | No |
| Multi-session groups + charts | Yes | No | Partial (queries / visuals) | Partial (cohorts / repository) | Partial (theme viz) |
| Saved analysis files you can reopen or script | Yes | No | No | Partial (exports) | Partial (CSV / JSON site data) |
| Jeffersonian / CA / GAT transcription | No | Partial (pauses, overlap, timestamps) | No | No | No |
| Public digital exhibit | No | No | No | Partial (share / reports) | Yes |
| Local LLM (Ollama) | Yes | No | No | No | No |

### Conversation analysis / EMCA resources

**[Transcription Resources](https://emcawiki.net/Transcription_Resources)** on emcawiki is a **catalogue**, not a product: Jeffersonian and related conventions, software comparison (ELAN, CLAN, EXMARaLDA, Transana, f4, InqScribe, DOTE, …), and teaching links. Those tools exist to produce **talk-in-interaction transcripts** (overlap alignment, pause timing, multimodal tiers) for conversation analysis.

**Choose them when** the artefact *is* a Jefferson / GAT / Mondada transcript (or an ELAN/CLAN project tied to media).

**Choose TranscriptX when** you already have timed speaker segments and want computational analysis. TranscriptX does not implement CA notation, partitur editors, or CHAT/EAF round-trips. A possible pipeline is CA tool → subtitle/text export → TranscriptX import, accepting that CA markup will not survive as first-class structure.

### CAQDAS (NVivo, MAXQDA, ATLAS.ti, Quirkos)

**[NVivo](https://lumivero.com/products/nvivo/)**, **[MAXQDA](https://www.maxqda.com/)**, and **[ATLAS.ti](https://atlasti.com/)** are the established **computer-assisted qualitative data analysis** packages: hierarchical codes, memos, queries, mixed-methods links, team projects. **[Quirkos](https://www.quirkos.com/)** is a simpler visual (bubble) coder aimed at students and smaller thematic projects. Open-source cousins such as [QualCoder](https://github.com/ccbogel/QualCoder) sit in the same job (noScribe’s author contributes there). [noScribe](https://noscribe.de/en/) HTML/TXT and [aTrain](https://github.com/aTrainTranscription/aTrain) QDA-formatted TXT are designed to **import** into these apps; some packages also add optional AI coding or cloud collaboration.

**Choose them when** the method requires a researcher-owned codebook, retrieval of coded segments, and an audit trail of human interpretation.

**Choose TranscriptX when** you want automatic, repeatable modules (language, speakers, interaction, emotion, voice, groups) and file-backed exports — not a replacement for coding. You can run TranscriptX first for computational views, then code in CAQDAS (or the reverse); they do not substitute for each other.

### AI qualitative research SaaS (DoReveal, Dovetail)

**[DoReveal](https://doreveal.com/)** (Synthefai) is hosted **end-to-end qualitative research** software: transcribe IDIs/focus groups, redact PHI/PII, structured analysis grids, thematic synthesis, agentic chat, quotes/clips, personas/journey maps, Jobs-to-Be-Done / emotional laddering, and generated reports. Aimed at research agencies and in-house insight teams.

**[Dovetail](https://dovetail.com/)** is a **customer-intelligence / research repository**: transcripts and recordings become a tagged, searchable org evidence base, with highlights, themes, AI chat, and stakeholder-facing docs/clips. Stronger on cross-study memory and product/UX collaboration than on a single-study CAQDAS codebook.

**Choose them when** team synthesis, discussion-guide-aware analysis, or a shared research repository is the product.

**Choose TranscriptX when** the corpus must stay on your machine, you want modular computational analytics rather than AI-authored insight decks, and you do not need multi-user SaaS.

### Oral History as Data

**[Oral History as Data](https://oralhistoryasdata.github.io/)** (University of Idaho CDIL; MIT; CollectionBuilder + GitHub Pages) is a **publishing framework**: you format interviews as CSV (speaker, words, optional tags, timestamps), link media, and ship a static exhibit with colour-coded thematic visuals. It is not an STT engine and not a CAQDAS.

**With TranscriptX:** analyse locally, then (if you want a public collection) reshape exports into OHD’s CSV. TranscriptX does not generate the exhibit site.

**Not a substitute for:** TranscriptX’s analysis pipeline, or for CAQDAS coding beyond simple spreadsheet tags.

## Narrow open-source demos

Smaller public projects often illustrate a **single wedge** (RAG chat, MoM extraction, rubric scoring, multi-perspective Q&A) rather than a full analysis workbench. They can be inspiring for presentation patterns; they are not TranscriptX substitutes for multi-module, multi-session, contract-backed analysis.

## Choosing in one glance

```text
Need STT from audio on my machine *today*?
  → Scriberr / noScribe / aTrain / WhisperX / …  then optionally → TranscriptX
  (TranscriptX may add optional local STT in 1.x — see ROADMAP)

Need confidential interview STT with a correction editor (qual research)?
  → noScribe  then optionally → TranscriptX (import VTT) and/or CAQDAS

Need confidential interview STT with MAXQDA / ATLAS.ti / NVivo-ready files (and optional CUDA)?
  → aTrain  then CAQDAS and/or TranscriptX (import TXT/JSON)

Need to dictate into whatever app is focused (not analyse a corpus)?
  → Amical

Need org-grade self-hosted live + batch STT (NVIDIA GPU, on-prem)?
  → Nanosamurai  then optionally → TranscriptX

Need desktop live capture of anything playing on the machine, or files up to 50 GB, plus a hosted editor?
  → RiverScript  then optionally → TranscriptX (import SRT/VTT)

Need Jeffersonian / CA / GAT transcripts or multimodal tiers?
  → EMCA wiki tools (ELAN, CLAN, EXMARaLDA, …)

Need bots + team notes tomorrow?
  → Otter / Fireflies / Avoma

Need sales CI + CRM?
  → Gong / Chorus / Avoma

Need contact-center QA at scale?
  → CallMiner / Observe.ai

Need to code interviews yourself (codebook, memos, retrieval)?
  → NVivo / MAXQDA / ATLAS.ti / Quirkos (or QualCoder)

Need hosted AI synthesis or a team research repository?
  → DoReveal / Dovetail

Need a public coded oral-history website?
  → Oral History as Data

Need local modular analysis of transcripts I control?
  → TranscriptX
```

## Related docs

- [How TranscriptX compares](comparison.md) — short answer and positioning
- [PRODUCT.md](PRODUCT.md) — product definition
- [ROADMAP.md](ROADMAP.md) — 1.x themes (including optional in-app STT)
- [transcription.md](runtime/transcription.md) — external STT workflows
- [known_limitations.md](known_limitations.md) — public limits

Maintainer research notes (not user-facing) may live under `.local/`; this page is the public comparison appendix.
