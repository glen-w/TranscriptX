# How TranscriptX compares

A plain-language map of where TranscriptX sits next to transcription tools, meeting assistants, conversation-intelligence products, and qualitative-research software.

**Last reviewed:** 2026-09-02. Feature lists for other products are based on public docs and positioning — not paid pilots.

Vendor-by-vendor research lives in the [comparison reference](comparison-reference.md). Prefer this page for “is this the right tool?”

## Short answer

| If you need… | Look at… |
|--------------|----------|
| Deep, local analysis of transcripts you already have | **TranscriptX** |
| Self-hosted audio → text (diarization, reader, optional chat) | **[Scriberr](https://scriberr.app/)** or WhisperX / similar |
| Local interview STT for sensitive qualitative research | **[noScribe](https://noscribe.de/en/)**, **[aTrain](https://github.com/aTrainTranscription/aTrain)** |
| Local dictation / push-to-talk into any app | **[Amical](https://amical.ai/)** |
| Org-grade self-hosted live + batch STT (GPU, on-prem) | **[nanosamur.ai](https://nanosamur.ai)** |
| Capture any app’s audio / huge files without a meeting bot | **[RiverScript](https://riverscript.com/)** |
| Jeffersonian / CA / GAT transcription conventions and tools | **[EMCA wiki: Transcription Resources](https://emcawiki.net/Transcription_Resources)** (then ELAN, CLAN, EXMARaLDA, …) |
| Auto-join Zoom/Meet notes + team sharing | Otter, Fireflies, Avoma |
| Sales deal coaching + CRM outcomes | Gong, Chorus by ZoomInfo |
| Contact-center QA / omnichannel coaching | CallMiner, Observe.ai |
| Researcher-applied coding, memos, codebooks (CAQDAS) | NVivo, MAXQDA, ATLAS.ti, Quirkos |
| Hosted AI qualitative synthesis / research repository | [DoReveal](https://doreveal.com/), [Dovetail](https://dovetail.com/) |
| Publish coded oral histories as a public digital exhibit | **[Oral History as Data](https://oralhistoryasdata.github.io/)** |

TranscriptX does **not** replace a transcription engine, a meeting bot, or a qualitative coding environment. It sits **after** you have transcript files, and focuses on **analysis**: language, speakers, interactions, emotion, voice, themes, groups, and exports you keep — on your machine.

Product definition: [PRODUCT.md](PRODUCT.md). Bring-your-own transcripts: [transcription.md](runtime/transcription.md).

## Where TranscriptX sits

Most tools in this space optimise one or more of:

1. **Ingest** — record or join meetings; run speech-to-text
2. **Present** — readable notes, search, chat over meetings
3. **Integrate** — CRM, calendars, team rollouts
4. **Analyze** — language, speakers, interaction, comparing several conversations over time
5. **Code (researcher-applied)** — codebooks, memos, highlights, thematic grids (CAQDAS / AI-qual)

TranscriptX is built for **(4)**, with a local-first library and optional local AI (Ollama). Transcription is **external** by design. Self-hosted tools such as [Scriberr](https://github.com/rishikanthc/Scriberr), [noScribe](https://github.com/kaixxx/noScribe), [aTrain](https://github.com/aTrainTranscription/aTrain), and [nanosamur.ai](https://github.com/nanosamurai/nanosamurai), and hosted capture workspaces such as [RiverScript](https://riverscript.com/), are natural **upstreams**: produce transcripts, then import into TranscriptX. CAQDAS and AI-qual tools sit **beside** TranscriptX (different analysis job), not as STT substitutes.

```text
Audio / meetings  →  STT / notes tool  →  transcript files  →  TranscriptX analysis
                         ↑                                      ↘ optional: CAQDAS / exhibit
              Scriberr, noScribe, aTrain, nanosamur.ai, RiverScript,
              WhisperX, Otter export, …
```

## Capability snapshot

Legend: **Yes** = first-class · **Partial** = adjacent or lighter · **No** = absent or out of scope.

| Capability | TranscriptX | STT / capture tools | Meeting assistants | CAQDAS / AI-qual |
|------------|-------------|---------------------|-------------------|------------------|
| Local / air-gapped analysis | Yes | Often yes (self-hosted STT) | No | Partial (desktop apps) |
| Built-in speech-to-text | No (BYO) | Yes | Yes | Partial |
| Meeting bot / auto-join | No | No (or system-audio instead) | Yes | No |
| Language, speakers, and interaction analysis | Yes | No | Partial | No |
| Researcher coding / codebook / memos | No | No | No | Yes |
| Saved analysis files you can reopen or script | Yes | Partial | No | Partial |
| Local LLM (Ollama) | Yes | Sometimes | No | No |

Vendor-level cells (Scriberr, Nanosamurai, RiverScript, Gong, …): [comparison reference](comparison-reference.md#capability-snapshot).

## What TranscriptX does not do today

Aligned with [PRODUCT.md](PRODUCT.md):

- Built-in transcription or meeting bots (bring your own files)
- A hosted multi-user analysis service
- Cloud AI as the default (Ollama on your machine is optional)
- Chat-over-corpus as the main product
- CRM / revenue-pipeline platforms
- Researcher coding with codebooks and memos
- Jeffersonian / GAT conversation-analytic transcription
- Public oral-history exhibit sites

**Post-1.0 direction:** optional local in-app transcription is tracked as a 1.x theme in [ROADMAP.md](ROADMAP.md) — it does not change the 1.0 BYO stance.

Limits users should know: [known_limitations.md](known_limitations.md).

## Choosing in one glance

```text
Need STT from audio on my machine *today*?
  → Scriberr / noScribe / aTrain / WhisperX / …  then optionally → TranscriptX

Need confidential interview STT with a correction editor (qual research)?
  → noScribe  then optionally → TranscriptX (import VTT) and/or CAQDAS

Need to dictate into whatever app is focused (not analyse a corpus)?
  → Amical

Need bots + team notes tomorrow?
  → Otter / Fireflies / Avoma

Need to code interviews yourself (codebook, memos, retrieval)?
  → NVivo / MAXQDA / ATLAS.ti / Quirkos (or QualCoder)

Need local modular analysis of transcripts I control?
  → TranscriptX
```

More branches (org-grade STT, RiverScript, sales CI, hosted AI-qual, oral-history exhibits): [comparison reference](comparison-reference.md#choosing-in-one-glance).

## Related docs

- [PRODUCT.md](PRODUCT.md) — product definition
- [Comparison reference](comparison-reference.md) — vendor notes and research
- [transcription.md](runtime/transcription.md) — external STT workflows
- [known_limitations.md](known_limitations.md) — public limits
