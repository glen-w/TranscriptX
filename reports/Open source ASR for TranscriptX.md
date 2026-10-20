# Plug open ASR without forcing diarization

**TranscriptX should keep Whisper-class host orchestration (whispermlx + WhisperX Docker) as the only Run-in-app STT surface, treat NVIDIA Parakeet/Canary as the next Theme K→H5 ladder rather than a Whisper replacement, and park Xiaomi CocktailASR-1 as an optional enrolled focus-speaker plugin—not a multi-speaker meeting engine.** Industry pipelines already treat undiarized captions as first-class content; TranscriptX has softened named-vs-unnamed gating but still hard-blocks most analysis when speaker fields are absent. The highest-leverage product move is a four-tier capability ladder (undiarized → synthetic monologue → diarized unnamed → named) that keeps default policy on named speakers while making T0/T1 resilient skips honest. Theme H1–H4 and Theme K command-gen are already shipped; the thickened *next* roadmap section after Now should elevate undiarized resilience plus Parakeet Theme K converters ahead of new providers, with CocktailASR on a research watchlist only. Engines stay outside the analysis image; BYO import remains the admission gate; no silent cloud STT.

## Whisper stays primary; Parakeet climbs the next rung

Beyond OpenAI Whisper and its runtimes, the production-relevant open-source ASR set for late 2025–2026 is **NVIDIA NeMo Parakeet/Canary** (and Canary-Qwen), **FunASR/SenseVoice**, **Moonshine**, **Distil-Whisper**, **sherpa-onnx**, and mature **Vosk/Kaldi**—with Meta SeamlessM4T and MMS capable but **CC-BY-NC**, which blocks many commercial local deployments ([Open ASR Leaderboard paper](https://arxiv.org/html/2510.06961v1); [NVIDIA-NeMo/Speech](https://github.com/nvidia-nemo/speech); [FunASR](https://github.com/modelscope/FunASR/); [moonshine-ai/moonshine](https://github.com/moonshine-ai/moonshine); [k2-fsa/sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)). On long-form open-source tracks, Whisper Large-v3 still led accuracy among OSS (**avg WER 6.43**), while **Parakeet CTC 1.1B** and **Parakeet TDT 0.6B v2** traded modestly higher WER for far higher throughput (**RTFx ~2794** and **~956**) ([Open ASR Leaderboard paper, Table 5](https://arxiv.org/html/2510.06961v1)). Canary-Qwen-2.5B and Parakeet TDT 0.6B v3 sit near the top of English aggregator boards (**~5.63%** and **~5.66%** mean WER) under **CC-BY-4.0** weights that permit commercial local use with attribution ([nvidia/canary-qwen-2.5b](https://huggingface.co/nvidia/canary-qwen-2.5b); [nvidia/parakeet-tdt-0.6b-v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3); [speechtotext.dev](https://speechtotext.dev/)).

TranscriptX’s architecture already matches how these stacks should land: **engines stay out of the analysis image**; the GUI orchestrates host **whispermlx** (macOS) or **WhisperX Docker**, or emits **Theme K** copyable commands; BYO import remains first-class ([docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md); [docs/runtime/transcription.md](../docs/runtime/transcription.md); [docs/ROADMAP.md](../docs/ROADMAP.md)). Theme **H1–H4** shipped that Whisper-class surface; **H5+** (Parakeet/Canary, YouTube URL ingest, HTTP sidecar) and **H6** streaming stay deferred until the Whisper path is boring ([docs/ROADMAP.md](../docs/ROADMAP.md)). Native multi-speaker labels remain rare: WhisperX and Whisper-WebUI compose **pyannote** (CC-BY-4.0 community weights); FunASR composes **CAM++**; NeMo’s Multitalker-Parakeet is the NVIDIA-native multi-speaker direction, otherwise ASR pairs with an external diarizer ([m-bain/whisperX](https://github.com/m-bain/whisperx); [FunASR model selection](https://www.funasr.com/en/docs/model-selection.html); [NeMo Featured Models](https://docs.nvidia.com/nemo/speech/latest/asr/featured_models.html)).

For plugin fit, the `TranscriptionProvider` protocol already expects an out-of-process job that writes a discoverable JSON path under `originals/`; managed import then normalizes WhisperX-shaped segments (`start`/`end`/`text` ± `speaker`/`words`) into canonical schema ([provider.py](../src/transcriptx/services/transcription/provider.py); [whisperx_engine.py](../src/transcriptx/io/import_adapters/json_vendor/whisperx_engine.py)). That yields a clear tier map: **Tier 1 (shipped providers)** = whispermlx + WhisperX Docker; **Tier 2 (Theme K now, H5 later)** = NeMo Parakeet/Canary via Docker/CLI plus a thin JSONL→WhisperX-shaped converter, plus optional faster-whisper/whisper.cpp and sherpa-onnx copy-commands; **Tier 3 (BYO/Copy only)** = Whisper-WebUI, FunASR/SenseVoice, Distil-Whisper, Vosk, Scriberr/noScribe/aTrain; **reject for commercial host orchestration** = SeamlessM4T/MMS (CC-BY-NC), in-process NeMo inside `transcriptx:latest`, silent cloud STT, DeepSpeech/Kaldi-as-product. Apple Silicon stays on MLX Whisper; CUDA servers get WhisperX Docker now and NeMo Docker later; CPU/edge favors Moonshine, Vosk, or sherpa-onnx—not as Balanced meeting defaults ([docs/runtime/transcription.md](../docs/runtime/transcription.md); [anvanvan/mac-whisper-speedtest](https://github.com/anvanvan/mac-whisper-speedtest)).

## CocktailASR locks one voice; it does not replace WhisperX

Xiaomi open-sourced **CocktailASR-1** as an Apache-2.0 inference repo plus a Hugging Face `trust_remote_code` checkpoint (`Ease3/Xiaomi-CocktailASR-1`, ~**35.6 GB** `pytorch_model.bin`) packaging a **~0.6B** Data2Vec2-style encoder, adapter, and **Qwen3-8B** backbone ([xiaomi-research/xiaomi-cocktailasr-1](https://github.com/xiaomi-research/xiaomi-cocktailasr-1); [Ease3/Xiaomi-CocktailASR-1](https://huggingface.co/Ease3/Xiaomi-CocktailASR-1); [arXiv:2609.11274](https://arxiv.org/abs/2609.11274)). The product contract is **target-speaker ASR (TS-ASR)**: given a short reference clip (training used **1–4 s**) concatenated internally with **1 s silence** then the mixture, the model transcribes **only** that enrolled speaker and returns **empty text** if the voice is absent—rejection rates on negative sets land in the mid-60s to high-70s percent, with low false-rejection on positive single-speaker sets ([GitHub README_en.md](https://raw.githubusercontent.com/xiaomi-research/xiaomi-cocktailasr-1/main/README_en.md); [arXiv:2609.11274](https://arxiv.org/html/2609.11274)). Reported WERs beat prior TS-ASR on LibriMix/LibriSpeechMix/AMI/AliMeeting while keeping single-speaker WER near Qwen3-ASR (e.g. LibriMix 2mix **4.11**, AMI SDM **21.81**, AliMeeting Far **20.63**) ([arXiv:2609.11274 Tables 1–4](https://arxiv.org/html/2609.11274)).

That is a different contract from WhisperX’s multi-speaker, time-aligned, anonymously labeled JSON. Classic cascades produce **SPEAKER_00…** for everyone; CocktailASR produces **one enrolled stream** (or nothing), with **no published word/segment timestamps** and optional CoT tags for speaker count/gender/similarity rather than diarization metadata ([GitHub README_en.md](https://raw.githubusercontent.com/xiaomi-research/xiaomi-cocktailasr-1/main/README_en.md); [FunASR diarization blog](https://www.funasr.com/en/blog/funasr-speaker-diarization.html)). Peers that stay closer to TranscriptX’s multi-speaker schema include **DiCoW** (Whisper conditioned on diarization masks), FunASR+CAM++, and pyannote+Whisper ([BUT-FIT/DiCoW_v3_3](https://huggingface.co/BUT-FIT/DiCoW_v3_3); [FunASR](https://github.com/modelscope/FunASR/)). Documented inference is **CUDA bfloat16** with `trust_remote_code=True`; treat the model as a heavy optional GPU plugin with hash-pinned local mirrors, not a default beside whispermlx ([HF model card](https://huggingface.co/Ease3/Xiaomi-CocktailASR-1)).

**Recommendation:** keep CocktailASR on a **research watchlist** as an optional “focus this enrolled speaker / cocktail-party extraction” path that would need enrollment UX, empty-output handling, and synthetic timing adapters—and explicitly **do not** position it as a WhisperX or Parakeet replacement for Balanced multi-speaker analysis.

## Admit undiarized text; gate interaction modules honestly

Leading consumer and caption pipelines treat plain SRT/VTT/TXT as first-class content for summaries and search. Otter still produces Action Items and AI Chat when speaker enrollment is off (diarization continues as Unknown / Speaker N); AssemblyAI defaults `speaker_labels` to **false**; YouTube auto-captions **never** include speakers; WhisperX diarization is an **opt-in** `--diarize` flag ([Otter: Disable Speaker Learning](https://help.otter.ai/hc/en-us/articles/40643231903639-Disable-Speaker-Learning); [AssemblyAI: Speaker Diarization](https://www.assemblyai.com/docs/pre-recorded-audio/label-speakers); [Potato: Annotate YouTube subtitles](https://www.potatoannotator.com/docs/guides/annotating-youtube-subtitles); [WhisperX README](https://github.com/m-bain/whisperX/)). Mature products separate **diarization** (partition turns) from **identification** (human names) and degrade honestly rather than refuse ingest.

TranscriptX already implements part of that ladder: default **named** speakers for meaningful Balanced runs; `analysis.allow_unnamed_speakers` (global) or the Run Analysis checkbox (per-run) ungates so diarized `SPEAKER_00` labels count; multi-speaker overview charts filter on monologues; skip reasons return strings instead of crashing ([docs/runtime/settings.md](../docs/runtime/settings.md); [module_registry.py](../src/transcriptx/core/pipeline/module_registry.py); [chart_registry.py](../src/transcriptx/core/utils/chart_registry.py)). The remaining hard edge is **T0 undiarized**: speaker-map creation refuses when all segments have `speaker: None`; most modules still declare `Requirement.SPEAKER_LABELS`; SRT/VTT import never mints a synthetic monologue speaker; and `allow_unnamed_speakers` cannot help a file with **zero** turn-taking labels ([speaker_mapping/core.py](../src/transcriptx/io/speaker_mapping/core.py); [canonical_transcript.py](../src/transcriptx/core/domain/canonical_transcript.py); [srt_engine.py](../src/transcriptx/io/import_adapters/subtitle/srt_engine.py)). Prefer post-hoc diarization (WhisperX `--diarize` or pyannote merge) when audio exists and interaction modules matter; accept undiarized text when audio is missing, cost dominates, or only global content modules are needed—and **never invent speakers without audio evidence** ([pyannoteAI: merge diarization and STT](https://docs.pyannote.ai/tutorials/diarization-asr-merge); [docs/runtime/transcription.md](../docs/runtime/transcription.md)).

The capability model that matches both industry practice and existing knobs is four tiers: **T0 Undiarized** (global topics/sentiment/readability/`llm_summary`/exports; skip all interaction/per-speaker with an Overview banner); **T1 Single synthetic speaker** (operator opts into “Treat as single speaker” → everything needing ≥1 speaker; still skip `requires_multiple_speakers`); **T2 Diarized unnamed** (shipped via ungate); **T3 Named** (default product policy). Content modules that still list `SPEAKER_LABELS` without needing turn structure should loosen that coupling; hard multi-speaker modules (conversation_loops, contagion, interactions, echoes, Q&A pairs) must keep requiring ≥2 turn-taking labels ([module_specs/conversation.py](../src/transcriptx/core/pipeline/module_specs/conversation.py); [docs/workflows/charts.md](../docs/workflows/charts.md)).

## Thickened next roadmap: resilience first, then Parakeet via Theme K

With H1–H4 and Theme K already shipping Whisper orchestration and copyable commands, the *next* post-Now product priority should not be a third registered provider. It should be **undiarized pipeline resilience (T0/T1)** plus a **Parakeet/Canary Theme K converter** that proves the admit path before any H5 registry work—and only then promote Parakeet to a CUDA Docker `TranscriptionProvider` once Whisper UX is boring. CocktailASR, HTTP sidecars, YouTube ingest, and H6 streaming stay below that cut. Decision forks stay locked: narrow Whisper-only Run-in-app until H5 entry criteria; engines outside the analysis image; no silent cloud STT; CocktailASR optional focus-speaker only.

## Conclusion

The open-source ASR landscape gives TranscriptX more engines than it needs as providers: Whisper-class remains the correct local default; Parakeet/Canary are the first serious throughput/multilingual upgrades once a WhisperX-shaped converter exists; CocktailASR is a strong enrolled-speaker research artifact that would break multi-speaker analytics if treated as a drop-in. Softening diarization is mostly a product-honesty problem TranscriptX is halfway through—T2/T3 work; T0/T1 do not. Elevating that ladder and Theme K Parakeet converters as the top post-Now STT priority keeps architecture constraints intact while making YouTube captions, Whisper-without-`--diarize`, and caption-only imports deliver content analysis instead of empty Balanced runs that look like bugs.

---

## Paste-ready: next ROADMAP section (after Now)

Coordinator can paste/adapt the block below into `docs/ROADMAP.md` as the top post-Now product priority (before or as the leading mid-1.x STT/product slice). Tables and forks are intentional paste targets.

```markdown
### Next (post-Now): Undiarized resilience + ASR plug-in ladder

**Priority:** First product work after Now, ahead of new Theme H providers.
Keep H1–H4 Whisper Run-in-app and Theme K command-gen as the shipped STT surface.
Do not register a third `TranscriptionProvider` until Whisper path is boring and the Parakeet admit converter has golden fixtures.

#### Capability ladder (speaker tiers)

| Tier | Signal | Runs | Skips / honesty | Status |
|------|--------|------|-----------------|--------|
| **T0 Undiarized** | No speaker field / all `None` | Global content: topics, wordclouds, readability, global sentiment, `llm_summary`, transcript_quality, exports | Interaction + per-speaker; Overview banner “No speaker labels” | **Next** — loosen `SPEAKER_LABELS` on content modules; never crash |
| **T1 Synthetic monologue** | User opts “Treat as single speaker” | Modules needing ≥1 speaker; per-speaker = whole-file | `requires_multiple_speakers` | **Next** — opt-in only; never invent without consent |
| **T2 Diarized unnamed** | `SPEAKER_00`… + `allow_unnamed_speakers` | Interaction + per-speaker under anonymous IDs | Named-only UX may stay limited | **Shipped** |
| **T3 Named speakers** | Human names via Speaker ID | Full Balanced/Thorough; profiles | None for speaker reasons | **Default policy** (keep) |

**Policy vs resilience:** default product policy stays T3 for meaningful Balanced runs.
Pipeline resilience must admit T0, skip with stable reasons, offer T1 and Theme H re-STT with `--diarize` to climb to T2.
Never invent T2 without audio.

#### Provider / command-gen tiers

| Tier | Engines | Action |
|------|---------|--------|
| **1 — Host providers (H)** | whispermlx (Mac), WhisperX Docker (CUDA/CPU) | Harden only until boring |
| **2 — Theme K → H5** | NeMo Parakeet TDT, Canary (± Canary-Qwen); optional faster-whisper / whisper.cpp / sherpa-onnx | Add copyable `docker run` + **WhisperX-shaped JSON converter** into `originals/`; Import remains gate; promote to registered provider only after H5 entry criteria |
| **3 — BYO / Copy recipes** | Whisper-WebUI, FunASR/SenseVoice, Distil-Whisper, Vosk, Scriberr/noScribe/aTrain | Document export→Import; adapters only if recurring shapes fail |
| **Watchlist** | CocktailASR-1 (focus-speaker / enrollment), HTTP STT sidecar, YouTube URL ingest (H5+), H6 streaming, DiCoW | Research / later; not Whisper replacements |
| **Reject** | In-process NeMo/Whisper in analysis image; silent cloud STT; SeamlessM4T/MMS as commercial defaults; DeepSpeech; Kaldi-as-product; meeting bots | Architecture / license / wrong job |

**CocktailASR-1 stance:** optional enrolled **focus-speaker** path only (reference clip → target-only text).
Not a multi-speaker diarized JSON replacement. Requires enrollment UX, empty-output handling, and timing adapters before any provider work. ~35 GB CUDA SpeechLLM; pin hashes / local mirror if ever enabled.

#### Decision forks (locked)

1. **Narrow Whisper Run-in-app** until H5 — no third provider for novelty.
2. **Engines outside analysis image** — Docker/host CLI only; Compose analysis never mounts STT.
3. **No silent cloud STT** — BYO import or explicit opt-in only.
4. **Theme K before H5 registry** — Parakeet/Canary converter + trust-matrix row + Mac honesty (“use whispermlx”) gate H5.
5. **Diarization optional** — content-first T0; Speakers-required is policy, not a crash.
6. **CocktailASR ≠ Whisper** — focus-speaker plugin or watchlist; never primary meeting ASR.

#### Concrete next slices

1. T0 content-only path + Overview honesty for speakerless SRT/VTT/Whisper-without-diarize.
2. T1 “Treat as single speaker” opt-in (import or Run Analysis).
3. Theme K: Parakeet (then Canary) command-gen + JSONL→`{segments:[{start,end,text,speaker?}]}` converter + golden fixtures.
4. H5 entry: converter + CUDA Docker recipe + trust/NOTICE row; then optional registered provider.
5. Defer CocktailASR / streaming / HTTP sidecar until (1)–(4) land.
```
