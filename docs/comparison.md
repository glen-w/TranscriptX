Type: GUIDE
Authority: docs/PRODUCT.md

# How TranscriptX compares

A plain-language map of where TranscriptX sits next to transcription tools, meeting assistants, and conversation-intelligence products.

**Last reviewed:** 2026-08-20. Feature lists for other products are based on public docs and positioning — not paid pilots. Prefer this page over scattered marketing claims elsewhere in the repo.

## Short answer

| If you need… | Look at… |
|--------------|----------|
| Deep, local, modular analysis of transcripts you already have | **TranscriptX** |
| Self-hosted audio → text (diarization, reader, optional chat) | **[Scriberr](https://scriberr.app/)** or WhisperX / similar |
| Org-grade self-hosted live + batch STT (GPU, on-prem) | **[nanosamur.ai](https://nanosamur.ai)** |
| Auto-join Zoom/Meet notes + team sharing | Otter, Fireflies, Avoma |
| Sales deal coaching + CRM outcomes | Gong, Chorus by ZoomInfo |
| Contact-center QA / omnichannel coaching | CallMiner, Observe.ai |

TranscriptX does **not** replace a transcription engine or a meeting bot. It sits **after** you have transcript files, and focuses on **analysis**: language, speakers, interactions, emotion, voice, themes, groups, and exportable structured results — on your machine.

Product definition: [PRODUCT.md](PRODUCT.md). Bring-your-own transcripts: [transcription.md](runtime/transcription.md).

## Where TranscriptX sits

Most tools in this space optimise one or more of:

1. **Ingest** — record or join meetings; run speech-to-text  
2. **Present** — readable notes, search, chat over meetings  
3. **Integrate** — CRM, calendars, team rollouts  
4. **Analyze** — discourse, affect, voice, multi-session science with contracts

TranscriptX is built for **(4)**, with a local-first library and optional local AI (Ollama). Transcription is **external** by design. Self-hosted tools such as [Scriberr](https://github.com/rishikanthc/Scriberr) and [nanosamur.ai](https://github.com/nanosamurai/nanosamurai) are natural **upstreams**: produce transcripts locally (or on-prem), then import into TranscriptX.

```text
Audio / meetings  →  STT / notes tool  →  transcript files  →  TranscriptX analysis
                         ↑
              Scriberr, nanosamur.ai, WhisperX, Otter export, …
```

## Capability snapshot

Legend: **Yes** = first-class · **Partial** = adjacent or lighter · **No** = absent or out of scope · **N/A** = not that product’s job.

| Capability | TranscriptX | Scriberr | Nanosamurai | Otter / Fireflies | Gong / Chorus / Avoma | CallMiner-class |
|------------|-------------|----------|-------------|-------------------|------------------------|-----------------|
| Local / air-gapped analysis | Yes | Yes (local mode) | Partial (self-hosted STT; NVIDIA GPU; not turnkey air-gap) | No | No | No |
| Built-in speech-to-text | No (BYO) | Yes | Yes (live + refine + final) | Yes | Yes (via capture) | Partial |
| Meeting bot / auto-join | No | No | No | Yes | Yes | Partial |
| Modular conversational analytics | Yes | No | No | Partial | Partial–Yes | Yes (CC domain) |
| Emotion / interaction / voice stacks | Yes | No | Partial (enrollment / diarization) | Partial | Partial | Yes (domain) |
| Multi-session groups + charts | Yes | No | No | Partial | Partial (deal/team) | Yes (agent/team) |
| Schema-versioned artifacts + Python API | Yes | Partial (API) | Partial (OpenAPI / SDK / protobuf) | No | No | No |
| CRM / revenue pipeline | No | No | No | Partial | Yes | Partial |
| Chat / Ask-AI over meetings | No (by design) | Yes | No | Yes | Yes | Partial |
| Local LLM (Ollama) | Yes | Yes | No | No | No | No |

## Complementary: self-hosted transcription

### Scriberr

- **Sites:** [scriberr.app](https://scriberr.app/) · [GitHub](https://github.com/rishikanthc/Scriberr)  
- **Fit:** Offline-friendly self-hosted transcription workspace — local models (e.g. Parakeet / Canary / Whisper-class), diarization, polished transcript reader, notes, folder watch / API, optional Ollama or OpenAI-compatible chat.  
- **With TranscriptX:** Use Scriberr to **create** transcripts; use TranscriptX to **analyse** a corpus over time.  
- **Not a substitute for:** TranscriptX’s module DAG, group analytics, or contract-backed research outputs.

### Nanosamurai

- **Sites:** [nanosamur.ai](https://nanosamur.ai) · [GitHub](https://github.com/nanosamurai/nanosamurai)  
- **Fit:** Apache-2.0 **org-grade speech platform** — browser UI + Windows Electron app, realtime captions with replaceable partials, asynchronous WhisperX refinement, canonical final transcripts with word timings and karaoke playback, speaker enrollment / diarization, PostgreSQL + object storage, Python SDK/CLI, optional Grafana/Tempo/Loki. Aimed at organisations that cannot send audio to a third party (on-prem / private cloud). Community Edition is a Docker Compose evaluator; default speech path expects an **NVIDIA GPU**. Agentic workflows and webhooks are public contracts, not shipped runners.  
- **With TranscriptX:** Use Nanosamurai to **capture and transcribe** sensitive sessions on infrastructure you control; export the **final** transcript (and recording) and import into TranscriptX to **analyse** a corpus. Personal / laptop-first STT is usually simpler with Scriberr or WhisperX.  
- **Not a substitute for:** TranscriptX’s analysis modules, groups, charts, or file-backed research contracts. Nanosamurai is capture + STT + session records, not conversational science.

### Other STT / subtitle paths

WhisperX, Whisper-WebUI (SRT/VTT), AssemblyAI, Deepgram, Otter exports, and manual JSON are all valid imports. Recipes: [WhisperX](recipes/whisperx/README.md), [Whisper-WebUI](recipes/whisper-webui/README.md).

## Meeting assistants (SaaS)

**Otter.ai**, **Fireflies.ai**, and similar products excel at **capture + same-day notes**: bots that join calls, live or near-live transcripts, searchable org libraries, and light “Ask AI” over meetings.

**Choose them when** team rollout and automatic recording matter more than local control or deep conversational science.

**Choose TranscriptX when** recordings or transcripts already exist (or come from a local STT tool), privacy / local retention matters, and you want structured multi-module analysis and exports you keep.

## Revenue & coaching conversation intelligence (SaaS)

**Gong**, **Chorus by ZoomInfo**, and **Avoma** productise **sales conversation intelligence**: talk patterns, trackers (objections, competitors, themes), scorecards, coaching, and CRM / pipeline hooks.

**CallMiner** (and adjacent tools such as Observe.ai) do analogous work for **contact centers**: scorecards, sequencing, omnichannel coverage, agent coaching.

**Choose them when** deal or agent outcomes tied to CRM/CCaaS are the product.

**Choose TranscriptX when** you want general conversational analytics without a sales or contact-center SaaS stack — still local, modular, and file-backed.

These vendors set a useful **UX bar** for trackers, talk ratios, and longitudinal views. TranscriptX does not aim to clone their capture/CRM platforms.

## Narrow open-source demos

Smaller public projects often illustrate a **single wedge** (RAG chat, MoM extraction, rubric scoring, multi-perspective Q&A) rather than a full analysis workbench. They can be inspiring for presentation patterns; they are not TranscriptX substitutes for multi-module, multi-session, contract-backed analysis.

## What TranscriptX does not do *today* (1.0)

Aligned with [PRODUCT.md](PRODUCT.md):

- Built-in transcription engine or meeting bots (BYO / command generation only)  
- Hosted multi-user SaaS analysis  
- Cloud LLM as the default product surface (Ollama / local today)  
- Chat-over-corpus as the primary product (RAG meeting assistant)  
- CRM / revenue-pipeline platforms  

**Post-1.0 direction:** optional local in-app transcription (NVIDIA / Whisper, CUDA/CPU, YouTube, directory watcher), karaoke-style playback, and an installable shell are tracked as 1.x themes in [ROADMAP.md](ROADMAP.md) — they do not change the 1.0 BYO stance.

Limits users should know: [known_limitations.md](known_limitations.md).

## Choosing in one glance

```text
Need STT from audio on my machine *today*?
  → Scriberr / WhisperX / …  then optionally → TranscriptX
  (TranscriptX may add optional local STT in 1.x — see ROADMAP)

Need org-grade self-hosted live + batch STT (NVIDIA GPU, on-prem)?
  → Nanosamurai  then optionally → TranscriptX

Need bots + team notes tomorrow?
  → Otter / Fireflies / Avoma

Need sales CI + CRM?
  → Gong / Chorus / Avoma

Need contact-center QA at scale?
  → CallMiner / Observe.ai

Need local modular analysis of transcripts I control?
  → TranscriptX
```

## Related docs

- [PRODUCT.md](PRODUCT.md) — product definition  
- [ROADMAP.md](ROADMAP.md) — 1.x themes (including optional in-app STT)  
- [USER_INDEX.md](USER_INDEX.md) — user doc map  
- [transcription.md](runtime/transcription.md) — external STT workflows  
- [known_limitations.md](known_limitations.md) — public limits  

Maintainer research notes (not user-facing) may live under `.local/`; this page is the public comparison surface.