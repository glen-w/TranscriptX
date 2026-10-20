# Open-source ASR / STT landscape for TranscriptX (late 2026)

Research date framing: primary sources checked against Oct 2025–2026 releases and docs. Notes are for a report writer synthesizing TranscriptX host-orchestrated STT vs BYO import (engines stay outside the analysis image).

## What are the leading open-source ASR stacks in 2025–2026 beyond classic Whisper?

### Takeaway
Beyond OpenAI Whisper and its runtimes (faster-whisper, WhisperX, whisper.cpp, mlx-whisper), the production-relevant OSS leaders in 2025–2026 are NVIDIA NeMo Parakeet/Canary (and Canary-Qwen), FunASR/SenseVoice (and Fun-ASR-Nano), Moonshine (edge/streaming), Distil-Whisper, sherpa-onnx (portable ONNX runtime over many models), and classic Vosk/Kaldi. Meta SeamlessM4T and MMS remain capable but are blocked for many commercial local apps by CC-BY-NC.

### Cited Findings
- Hugging Face Open ASR Leaderboard (paper, cutoff 8 Oct 2025) compares 60+ systems; of 64 listed models, 57 were open-source, from 18 organizations including NVIDIA (18), Meta (12), OpenAI (8), Hugging Face (5), Useful Sensors/Moonshine (2) — [Open ASR Leaderboard paper](https://arxiv.org/html/2510.06961v1); interactive board: [hf.co/spaces/hf-audio/open_asr_leaderboard](https://huggingface.co/spaces/hf-audio/open_asr_leaderboard).
- On long-form open-source tracks in that paper, Whisper Large-v3 led accuracy among OSS (avg WER 6.43, RTFx ~68.6), while NVIDIA Parakeet CTC 1.1B and Parakeet TDT 0.6B v2 traded modestly higher WER for far higher throughput (RTFx ~2794 and ~956) — [Open ASR Leaderboard paper, Table 5](https://arxiv.org/html/2510.06961v1).
- NVIDIA NeMo Speech (Apache-2.0 toolkit) actively ships Parakeet V3 and Canary V2 (25 EU languages, Aug 2025), Canary-Qwen-2.5B (~5.63% English Open ASR Leaderboard mean WER claimed), Parakeet-unified streaming/offline (2026), and Nemotron speech streaming (2026) — [NVIDIA-NeMo/Speech README](https://github.com/nvidia-nemo/speech); [Featured Models docs](https://docs.nvidia.com/nemo/speech/latest/asr/featured_models.html).
- FunASR positions SenseVoiceSmall, Fun-ASR-Nano, Fun-ASR-MLT-Nano, Paraformer, and third-party MOSS-Transcribe-Diarize as a modular toolkit (task/checkpoint/runtime chosen separately); toolkit MIT, model licenses per card — [modelscope/FunASR](https://github.com/modelscope/FunASR/).
- Moonshine is positioned as on-device / low-latency ASR with MIT code and (by default) MIT models; English Tiny/Base and all streaming STT models are MIT — [moonshine-ai/moonshine](https://github.com/moonshine-ai/moonshine); [LICENSE](https://github.com/moonshine-ai/moonshine/blob/main/LICENSE).
- Distil-Whisper (Hugging Face) claims ~6× faster / ~50% smaller than Whisper with WER within ~1% of teacher, MIT-licensed — [huggingface/distil-whisper](https://github.com/huggingface/distil-whisper).
- sherpa-onnx (next-gen Kaldi + ONNX Runtime) is a multi-language offline runtime for ASR, VAD, diarization, TTS, etc., used to ship Whisper, SenseVoice, NeMo, Zipformer, Moonshine and other converted models — [k2-fsa/sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx); [speaker diarization docs](https://k2-fsa.github.io/sherpa/onnx/speaker-diarization/index.html).
- STT Index aggregator (verify per-model cards) lists top English Open ASR Leaderboard averages including ARK-ASR ~4.64%, Canary-Qwen 2.5B ~5.63%, Parakeet TDT 0.6B v3 ~5.66%, Granite Speech 3.3 8B ~5.74% — [speechtotext.dev](https://speechtotext.dev/).
- Amical is an MIT local-first *dictation app* powered by Whisper + Ollama, not a standalone transcription engine — [amicalhq/amical](https://github.com/amicalhq/amical); [amical.ai](https://amical.ai/). Treat as a consumer of engines, not an engine.

### Inferences
- For TranscriptX-class offline meeting/long-form work, the competitive set is: Whisper-family runtimes (accuracy + ecosystem), NeMo Parakeet/Canary (accuracy/throughput, CUDA-first), FunASR/SenseVoice (CJK + emotion/events + optional diarization pipeline), and sherpa-onnx/Vosk (edge/CPU/embeddable).
- “Leading” should be split by hardware: Apple Silicon → mlx-whisper / whisper.cpp / FluidAudio-Parakeet CoreML; CUDA servers → faster-whisper, WhisperX, NeMo; CPU/edge → Moonshine, Vosk, sherpa-onnx, quantized whisper.cpp.

### Gaps
- Independent head-to-head WER on the same long-form multi-speaker meeting corpus for Parakeet v3 vs Whisper large-v3-turbo vs SenseVoice vs Moonshine was not located in a single primary study for this note set; rely on Open ASR Leaderboard + vendor cards.
- ARK-ASR / Granite Speech / Cohere Transcribe appear on aggregator boards but were not deep-verified against license texts in this pass.

---

## Inventory of named engines (license, home, WER, timestamps, speakers, Docker/CLI, hardware)

### Takeaway
Permissive local-use stacks cluster around MIT/Apache/BSD/CC-BY for Whisper-family, NeMo Parakeet/Canary weights (CC-BY-4.0), Distil-Whisper, Vosk (mostly Apache), FunASR toolkit (MIT), and Moonshine MIT models. Flag CC-BY-NC (SeamlessM4T, Meta MMS), FunASR Model License nuances for SenseVoice weights, Moonshine Community License for legacy non-English non-streaming models, and AGPL for some Vosk models. Native speaker labels are rare; most stacks compose pyannote, CAM++, or sherpa diarization as a separate pipeline.

### Cited Findings

#### Whisper family (baseline + runtimes)
- **openai/whisper** — MIT; multilingual ASR + translation; utterance/segment timestamps natively; no native multi-speaker diarization; PyTorch; CPU/CUDA/MPS — [openai/whisper](https://github.com/openai/whisper) (license historically MIT; Distil-Whisper inherits MIT from Whisper — [distil-whisper LICENSE](https://github.com/huggingface/distil-whisper/blob/main/LICENSE)).
- **SYSTRAN/faster-whisper** — CTranslate2 reimplementation; up to ~4× faster than openai/whisper at same accuracy; int8 on CPU/GPU; strong CUDA path; weaker on Apple Silicon (CPU fallback) — [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper); Mac comparative measurements — [pareido.jp Whisper comparison](https://pareido.jp/architecture/ai/ai-voice/whipsers-comparison/).
- **m-bain/whisperX** — BSD-2-Clause code; batched faster-whisper backend; word-level timestamps via wav2vec2 forced alignment; optional pyannote diarization (`--diarize`, HF token + model agreement); claims ~70× realtime with large-v2; outputs JSON/segments with words/speakers; VAD batching — [m-bain/whisperX](https://github.com/m-bain/whisperx); [LICENSE](https://github.com/m-bain/whisperX/blob/main/LICENSE); diarization uses pyannote community models (CC-BY-4.0) — [whisperx.app/licensing](https://whisperx.app/licensing).
- **ggml-org/whisper.cpp** — MIT; C/C++ CLI/library; Metal/CoreML/CUDA/OpenVINO/CPU; outputs txt/vtt/srt/lrc/csv/json; word-ish timing via `--max-len 1` / `--split-on-word` / experimental DTW token timestamps; stereo/tinydiarize flags exist but are limited vs pyannote — [ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp/); [LICENSE](https://github.com/ggml-org/whisper.cpp/blob/master/LICENSE); [CLI options](https://github.com/ggml-org/whisper.cpp/tree/master/examples/cli).
- **mlx-whisper** — Apple MLX Python path; typically fastest Whisper runtime on Apple Silicon in third-party benches (e.g. large-v3-turbo ~1.93s vs whisper.cpp ~4.21s on ~58s audio in one Mac M5 test) — [pareido.jp comparison](https://pareido.jp/architecture/ai/ai-voice/whipsers-comparison/); multi-impl Mac bench also shows mlx-whisper and Parakeet-MLX/CoreML ahead of faster-whisper-on-CPU — [anvanvan/mac-whisper-speedtest](https://github.com/anvanvan/mac-whisper-speedtest).
- **jhj0517/Whisper-WebUI** — Apache-2.0 Gradio UI wrapping openai-whisper / faster-whisper / insanely-fast-whisper; SRT/WebVTT/txt; Silero VAD; optional UVR; pyannote diarization post-process; Docker Compose (~7GB image), Hub image `jhj0517/whisper-webui` — [jhj0517/Whisper-WebUI](https://github.com/jhj0517/Whisper-WebUI); [docker-compose.yaml](https://github.com/jhj0517/Whisper-WebUI/blob/master/docker-compose.yaml).

#### Distil-Whisper
- Repo/models MIT; English-focused distilled Whisper; segment-level timestamps via `return_timestamps=True`; maintainers state word-level timestamp heads were **not** distilled (segment-level only) — [distil-whisper/distil-large-v3](https://huggingface.co/distil-whisper/distil-large-v3); [discussion on word timestamps](https://huggingface.co/distil-whisper/distil-large-v3.5/discussions/6); long-form Open ASR paper avg WER 7.27, RTFx ~153 — [Open ASR Leaderboard paper](https://arxiv.org/html/2510.06961v1).

#### NVIDIA NeMo Parakeet / Canary
- **Toolkit**: NeMo Speech Apache-2.0 — [NVIDIA-NeMo/Speech](https://github.com/nvidia-nemo/speech).
- **Weights**: Canary-1b-v2 and Parakeet-tdt-0.6b-v3 released under **CC-BY-4.0** (commercial OK with attribution) — [nvidia/canary-1b-v2](https://huggingface.co/nvidia/canary-1b-v2); Parakeet v3 card notes CC BY 4.0 — [parakeet-tdt-0.6b-v3 commit](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3/commit/7938c10e1da61989cdd04d560b084b06d6e949fc).
- **Canary-1b-v2**: ASR + speech translation across 25 European languages; automatic punctuation/capitalization; **word-level and segment-level timestamps**; FastConformer encoder + Transformer decoder (~978M params); HF release dated 08/14/2025 — [nvidia/canary-1b-v2](https://huggingface.co/nvidia/canary-1b-v2).
- **Canary-Qwen-2.5B**: English ASR SALM; CC-BY-4.0; Open ASR Leaderboard mean WER **5.63**, RTFx **418** (vendor table); PnC; ASR mode + LLM post-process mode; HF 07/17/2025; CUDA-oriented NeMo install — [nvidia/canary-qwen-2.5b](https://huggingface.co/nvidia/canary-qwen-2.5b).
- **Parakeet family**: FastConformer + CTC/RNN-T/TDT; docs list TDT 0.6B v3 (timestamps, PnC; Featured Models page says 25 languages / blazing fast), TDT 0.6B v2 English, Multitalker-Parakeet, Nemotron streaming — [Featured Models](https://docs.nvidia.com/nemo/speech/latest/asr/featured_models.html); [ASR checkpoints table](https://docs.nvidia.com/nemo/speech/latest/asr/asr_checkpoints.html). Note: the checkpoints table row for `parakeet-tdt-0.6b-v3` lists Language “English” while Featured Models and HF marketing emphasize multilingual v3 — treat as a docs inconsistency to re-check before shipping.
- **Diarization**: not generally built into single-file Canary/Parakeet ASR; Multitalker-Parakeet is the NeMo multi-speaker direction — [Featured Models](https://docs.nvidia.com/nemo/speech/latest/asr/featured_models.html). Otherwise pair with pyannote or NeMo speaker models.
- **Hardware / ops**: Prefer NVIDIA CUDA + NeMo containers/NGC; Apple Silicon community ports exist (e.g. parakeet-mlx / FluidAudio CoreML in Mac speedtests) — [mac-whisper-speedtest](https://github.com/anvanvan/mac-whisper-speedtest). CLI/Python via `nemo_asr.models.ASRModel.from_pretrained(...)` — [ASR checkpoints](https://docs.nvidia.com/nemo/speech/latest/asr/asr_checkpoints.html).

#### Moonshine (Useful Sensors / Moonshine AI)
- Code MIT; models MIT by default including all streaming STT and English Tiny/Base; **legacy non-streaming** Arabic/Japanese/Korean/Mandarin/Spanish/Ukrainian/Vietnamese Tiny/Base remain under **Moonshine Community License** (research/non-commercial free; commercial registration; >$1M revenue needs enterprise) — [LICENSE](https://github.com/moonshine-ai/moonshine/blob/main/LICENSE); [docs license page](https://moonshine-voice.readthedocs.io/en/stable/license/); [community license text](https://www.moonshine.ai/moonshine_community_license.txt).
- Oriented to resource-constrained / real-time on-device ASR; claims WER better than similarly sized Whisper on OpenASR leaderboard datasets (vendor README via PyPI historical description) — [useful-moonshine PyPI](https://pypi.org/project/useful-moonshine/); repo: [moonshine-ai/moonshine](https://github.com/moonshine-ai/moonshine).
- Native speaker diarization: not a primary feature in sources reviewed; treat as ASR-only unless composed elsewhere.

#### FunASR / SenseVoice
- FunASR toolkit MIT; model zoo licenses separate — [FunASR README](https://github.com/modelscope/FunASR/).
- **SenseVoiceSmall**: ASR + emotion/event tags; zh/en/ja/ko/yue; ~234M; word/token timestamps available with `output_timestamp=True` in SenseVoice demos; speaker labels come from composing `fsmn-vad` + `cam++` (anonymous per-recording clusters, not identity) — [FunASR model selection](https://www.funasr.com/en/docs/model-selection.html); [SenseVoice demo_spk.py](https://github.com/modelscope/FunASR/blob/main/examples/industrial_data_pretraining/sense_voice/demo_spk.py); [FunAudioLLM/SenseVoice](https://github.com/funaudiollm/sensevoice).
- SenseVoice maintainers clarify commercial use of official SenseVoiceSmall weights permitted under FunASR Model Open Source License Agreement when followed; check model card before redistribute — [SenseVoice README license section](https://github.com/funaudiollm/sensevoice) (via search synthesis of that README).
- **Fun-ASR-Nano / Fun-ASR-MLT-Nano**: LLM-based ASR paths; Nano zh/en/ja + Chinese dialects; MLT-Nano 31 languages; timestamp support depends on checkpoint/path — [FunASR](https://github.com/modelscope/FunASR/).
- **MOSS-Transcribe-Diarize**: third-party OpenMOSS offline joint text + timestamps + anonymous speakers via FunASR adapter — [FunASR](https://github.com/modelscope/FunASR/).
- Docker/CLI: FunASR Python `AutoModel`, WebSocket streaming services, GGUF/llama.cpp paths for Nano/SenseVoice — [FunASR](https://github.com/modelscope/FunASR/); GPU preferred, CPU smoke tests documented.

#### SeamlessM4T (Meta)
- ASR among S2ST/S2TT/T2ST/T2TT tasks; ~100 language coverage (v1: 101 speech-in / 96 text) — [facebookresearch/seamless_communication](https://github.com/facebookresearch/seamless_communication); [seamless-m4t-large](https://huggingface.co/facebook/seamless-m4t-large).
- **Models CC-BY-NC 4.0** (non-commercial); some non-generative components MIT; “Seamless” branded models under separate Seamless license (noncommercial research) — [repo License section](https://github.com/facebookresearch/seamless_communication); [HF v2 card license](https://huggingface.co/facebook/seamless-m4t-v2-large/blob/dff1eae6b5ed4de138247d6d6c5a37ef6ae20d46/README.md); [Meta Seamless TOS](https://ai.meta.com/resources/models-and-libraries/seamless-license/).
- **Flag for TranscriptX commercial/local product use**: restrictive relative to Whisper/NeMo CC-BY.

#### Wav2Vec2 / HuBERT / MMS descendants
- Wav2Vec2 / HuBERT CTC ASR via Hugging Face Transformers; English HuBERT-large fine-tune widely used; forced-alignment role in WhisperX — [Wav2Vec2 docs](https://huggingface.co/docs/transformers/en/model_doc/wav2vec2); [hubert-large-ls960-ft](https://huggingface.co/facebook/hubert-large-ls960-ft).
- **facebook/mms-1b-all**: 1162 languages, Wav2Vec2+adapters, **CC-BY-NC 4.0** — [facebook/mms-1b-all](https://huggingface.co/facebook/mms-1b-all); [MMS docs](https://huggingface.co/docs/transformers/model_doc/mms).
- Typically emit frame/CTC alignments rather than rich meeting JSON; no native multi-speaker diarization; good as aligners or low-resource language ASR, weaker as drop-in WhisperX replacements for meetings.

#### Vosk / Kaldi
- Kaldi toolkit Apache-2.0 — [Kaldi legal](https://kaldi-asr.org/doc/legal.html).
- Vosk API offline ASR, 20+ languages/dialects, Apache-2.0 API; model licenses vary (most Apache 2.0; some AGPL/LGPL/GPL) — [alphacep/vosk-api](https://github.com/alphacep/vosk-api/); [Vosk models table](https://alphacephei.com/vosk/models) (e.g. vosk-model-en-us-0.22 WER 5.69 Librispeech test-clean / 6.05 TED-LIUM, Apache 2.0; daanzu models AGPL).
- Strong CPU/mobile/RPi story; word-level results via Kaldi lattices/partial results; speaker diarization not core Vosk feature.
- Mature but older accuracy vs 2025 Whisper/NeMo SOTA on broad English Open ASR boards.

#### sherpa-onnx
- Runtime Apache-2.0; offline ASR + VAD + speaker diarization + websocket servers; many languages/bindings; embeds converted Whisper/SenseVoice/NeMo/Zipformer/Moonshine etc. — [k2-fsa/sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx); [diarization docs](https://k2-fsa.github.io/sherpa/onnx/speaker-diarization/index.html).
- **Model licenses remain those of upstream weights**; maintainers defer redistribution questions to original authors — [Discussion #3939](https://github.com/k2-fsa/sherpa-onnx/discussions/3939). SenseVoice ONNX packages inherit FunASR Model License — [jpssff/sherpa-onnx-sense-voice](https://huggingface.co/jpssff/sherpa-onnx-sense-voice).
- Excellent host-sidecar candidate for CPU/edge when TranscriptX wants a single binary runtime without PyTorch.

#### Diarization pipelines (not ASR engines)
- **pyannote.audio**: MIT code; Community-1 pipeline weights **CC-BY-4.0** (commercial with attribution) — [pyannote LICENSE](https://github.com/pyannote/pyannote-audio/blob/develop/LICENSE); [pyannote build-vs-buy](https://www.pyannote.ai/blog/build-vs.-buy-the-real-cost-of-self-hosting-diarization).
- WhisperX and Whisper-WebUI both compose pyannote rather than inventing diarization — [whisperX README](https://github.com/m-bain/whisperx); [Whisper-WebUI README](https://github.com/jhj0517/Whisper-WebUI).
- FunASR uses CAM++ embeddings + clustering for anonymous speakers — [FunASR model selection](https://www.funasr.com/en/docs/model-selection.html).

### Inferences
- Best “meeting transcript” packages out of the box: WhisperX (or Whisper-WebUI) for words+speakers; FunASR SenseVoice+VAD+CAM++ or MOSS-Transcribe-Diarize for CJK-centric; NeMo Multitalker for NVIDIA-native multi-speaker (less ecosystem JSON familiarity for TranscriptX today).
- Best pure throughput English offline: Parakeet CTC/TDT (per Open ASR long-form RTFx).
- Best Apple Silicon Whisper path: mlx-whisper / whisper.cpp; Parakeet CoreML/MLX ports emerging for non-Whisper speed.
- Restrictive/RAIL-like flags: SeamlessM4T & MMS (CC-BY-NC); Moonshine Community (legacy multilingual); some Vosk AGPL models; SenseVoice FunASR Model License (read carefully for redistribution).

### Gaps
- Exact WER numbers for Moonshine Tiny/Base vs Whisper tiny/base on identical 2026 leaderboard snapshots were not re-fetched from a model card in this pass (vendor claims only).
- Parakeet-tdt-0.6b-v3 language coverage conflict between NeMo docs tables vs Featured Models / HF marketing needs a primary card re-read before product copy.
- No primary-source confirmation in this pass of native word timestamps for all Moonshine streaming variants.

---

## Which are realistic as host-orchestrated providers vs BYO import-only?

### Takeaway
TranscriptX already treats engines as outside the analysis image, with shipped host orchestration for whispermlx (macOS) and WhisperX Docker, plus Copy-command / BYO for Whisper-WebUI and other CLIs. Realistic next host-orchestrated providers are CLI/Docker-friendly stacks that emit importable JSON/SRT/VTT with optional word timings; heavy NeMo/FunASR stacks and HTTP sidecars fit “host provider later”; SaaS meeting bots and restrictive-license models should stay BYO-or-never.

### Cited Findings
- TranscriptX architecture: “Transcription engines stay out of the analysis image”; GUI can orchestrate host whispermlx or WhisperX Docker, or copy commands; BYO import remains first-class — repo docs [`docs/ARCHITECTURE.md`](../../../docs/ARCHITECTURE.md); [`docs/runtime/transcription.md`](../../../docs/runtime/transcription.md).
- Shipped Theme H: host-orchestrated Whisper-class STT (whispermlx, WhisperX Docker); H5+ NVIDIA Parakeet/Canary, YouTube URL ingest, HTTP STT sidecar deferred until Whisper path is boring — [`docs/ROADMAP.md`](../../../docs/ROADMAP.md).
- Preferred stack matrix: macOS → whispermlx; Linux/Windows → WhisperX Docker / WebUI; Whisper-WebUI hand-off is SRT/VTT → Import — [`docs/runtime/transcription.md`](../../../docs/runtime/transcription.md).
- Compatible BYO formats today include WhisperX JSON, Scriberr, AssemblyAI, Deepgram, Otter, Google, Colab, SRT/VTT (Whisper-WebUI, RiverScript, noScribe), aTrain TXT/JSON — [`docs/runtime/transcription.md`](../../../docs/runtime/transcription.md).
- Whisper-WebUI and WhisperX already have TranscriptX recipes; WebUI is interoperability/Copy-command, not Run-in-app provider — [`docs/public_surfaces.md`](../../../docs/public_surfaces.md); comparison positions Scriberr/noScribe/aTrain as upstream producers — [`docs/comparison.md`](../../../docs/comparison.md).
- Docker/CLI friendliness signals from primary sources: WhisperX (CLI + Docker recipes in TranscriptX), Whisper-WebUI (Compose), faster-whisper (pip CLI), whisper.cpp (single binary), NeMo (pip + NGC containers), FunASR (Python AutoModel + services), sherpa-onnx (native binaries/APKs/websocket), Vosk (pip + model zip) — sources in prior sections.
- Meeting bots / SaaS (Otter, hosted WhisperX.app, Amical cloud modes, commercial pyannote API) are upstreams or alternatives, not TranscriptX-embedded engines — [whisperx.app](https://whisperx.app/); [amical.ai](https://amical.ai/); [`docs/comparison.md`](../../../docs/comparison.md).

### Inferences

**Strong host-orchestrated provider candidates (engine outside analysis image, subprocess/Docker):**
| Candidate | Why realistic | Notes for TranscriptX |
|---|---|---|
| whispermlx (shipped) | Apple MLX, PATH binary, already Run-in-app | macOS-only |
| WhisperX Docker (shipped) | CUDA/CPU, words+diarization JSON | Needs HF token for diarization models |
| faster-whisper / whisper.cpp | Thin CLI, MIT, easy Copy-command → possible provider | Add word/speaker via optional pyannote or accept segment-only |
| sherpa-onnx | Single offline runtime, websocket server option | Map ONNX model licenses carefully; normalize output schema |
| Moonshine (MIT models) | Light host binary for short/voice-note paths | Not ideal as sole long meeting engine; Community-license models excluded |
| NeMo Parakeet/Canary (H5 deferred) | Official roadmap; CC-BY weights; timestamps | Heavy CUDA/NeMo deps → Docker sidecar preferred over analysis image |

**Better as BYO import / Copy-command only (for now):**
| Candidate | Why |
|---|---|
| Whisper-WebUI | Gradio UX; already recipe as SRT/VTT hand-off; large image |
| FunASR SenseVoice / Fun-ASR-Nano | Excellent capability, but Model License + ModelScope/HF pull complexity; output schema differs |
| Distil-Whisper | Easy via faster-whisper/transformers, but segment timestamps only; little advantage overturbo Whisper as a dedicated provider |
| Vosk/Kaldi | Fine for constrained CPU BYO; weaker accuracy/ecosystem vs WhisperX JSON |
| Wav2Vec/HuBERT/MMS | Aligners or niche languages; MMS NC license |
| SeamlessM4T | CC-BY-NC — unsuitable for many commercial local deployments |
| Amical / Scriberr / noScribe / aTrain / RiverScript | Apps/upstreams, not engines to orchestrate |

**Provider vs import decision rule (inference):** Prefer host orchestration when (1) license is permissive for local commercial use, (2) install is Docker or single CLI, (3) output can be normalized to TranscriptX JSON with word timings (± speakers), (4) hardware path matches host OS matrix. Otherwise keep Copy-command + Import Transcript.

### Gaps
- No public TranscriptX adapter schema contract for Parakeet/Canary/FunASR JSON was found in this research pass beyond roadmap deferral — implementation details remain product design.
- FluidAudio / Parakeet-CoreML maturity as a first-class macOS provider (beyond speedtest repos) was not validated against release stability docs.

---

## Compact comparison matrix (synthesis for report writer)

| Engine / stack | License (code / weights) | Word times | Speakers | Hardware sweet spot | Maturity | Host provider? | BYO? |
|---|---|---|---|---|---|---|---|
| OpenAI Whisper | MIT / MIT | Segment | No (compose) | CPU/CUDA/MPS | High | Possible | Yes |
| faster-whisper | MIT path | Segment (+token opts) | No | CUDA, CPU | High | Strong | Yes |
| WhisperX | BSD-2 / Whisper+pyannote | Yes (align) | Yes (pyannote) | CUDA | High | **Shipped** | Yes |
| whisper.cpp | MIT | Approx / experimental | Limited | Metal/CPU/CUDA | High | Strong CLI | Yes |
| mlx-whisper | (MLX ecosystem) | Whisper-like | No | Apple Silicon | High | **Shipped** (whispermlx) | Yes |
| Distil-Whisper | MIT | Segment only | No | CUDA/CPU | Medium-High | Weak need | Yes |
| NeMo Parakeet | Apache / CC-BY-4.0 | Yes (TDT etc.) | Multitalker / compose | CUDA (+MLX ports) | High & rising | Roadmap H5 | Yes |
| NeMo Canary / Canary-Qwen | Apache / CC-BY-4.0 | Yes (Canary) | Compose | CUDA | High | Roadmap H5 | Yes |
| Moonshine | MIT / MIT (+Community legacy) | Unclear/partial | No | Edge/CPU | Medium | Niche | Yes |
| FunASR SenseVoice | MIT / FunASR Model License | Yes (optional) | Via CAM++ | CUDA/CPU | High (CN ecosystem) | Later sidecar | Yes |
| SeamlessM4T | MIT bits / **CC-BY-NC** | Task-dependent | No | CUDA | Medium | Avoid commercial | Research only |
| MMS (Wav2Vec) | **CC-BY-NC** | CTC frames | No | CUDA/CPU | Medium | Avoid commercial | Niche |
| Vosk | Apache / per-model | Partial | No | CPU/mobile | Mature-legacy | Unlikely | Yes |
| sherpa-onnx | Apache / upstream | Model-dependent | Yes (built-in pipeline) | CPU/edge/NPU | High | Strong sidecar | Yes |
| Whisper-WebUI | Apache-2.0 wrapper | Via backend | pyannote | CUDA/CPU Docker | Medium | Copy-cmd recipe | **Primary** |

Sources for matrix cells are the cited findings above; cells marked “Unclear/partial” are explicit gaps, not inventiveness.
