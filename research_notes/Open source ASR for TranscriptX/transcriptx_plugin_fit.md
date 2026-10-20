# Open source ASR for TranscriptX — plugin fit

Dense mapping of TranscriptX STT contracts to candidate engines. Architecture constraints (locked): engines outside the analysis image; no silent cloud STT; host-orchestrated providers only; BYO import remains the default admission gate.

---

## What is the TranscriptionProvider interface / job store / whispermlx + WhisperX Docker path today?

### Takeaway
Theme H1–H4 is shipped as a narrow Whisper-class host-orchestration surface: a `TranscriptionProvider` protocol, two registered providers (`whispermlx`, `whisperx_docker`), a file-backed job store under `data_dir/transcription/jobs/`, and GUI **Run in app** / watcher `auto_transcribe`. Theme H5+ (Parakeet/Canary, YouTube, HTTP sidecar) and H6 (streaming) are explicitly deferred.

### Cited Findings
- `TranscriptionProvider` is a Protocol requiring `provider_id`, `info()`, `is_available(options)`, and `transcribe(audio_path, output_dir, options) -> TranscriptionProviderResult` — [provider.py](file:///Users/89298/Documents/transcriptx/src/transcriptx/services/transcription/provider.py)
- Registry hard-codes only `WhisperMLXProvider` and `WhisperXDockerProvider`; default fallback id is `whispermlx` — [registry.py](file:///Users/89298/Documents/transcriptx/src/transcriptx/services/transcription/registry.py)
- `TranscriptionOptions` carries `provider_id`, `model`, `language`, `diarize`, timeout, `device`/`compute_type`/`batch_size`, speaker bounds, and `docker_image` (default `ghcr.io/m-bain/whisperx:latest`); secrets are not in the options object — [requests.py](file:///Users/89298/Documents/transcriptx/src/transcriptx/app/models/requests.py)
- Provider success contract is a JSON file path (`TranscriptionProviderResult.json_path`), not an in-memory transcript — [results.py](file:///Users/89298/Documents/transcriptx/src/transcriptx/app/models/results.py)
- Job store persists queued/running/succeeded/failed/cancelled records as atomic JSON under `data_dir/transcription/jobs/` — [job_store.py](file:///Users/89298/Documents/transcriptx/src/transcriptx/services/transcription/job_store.py); [ROADMAP Theme H](file:///Users/89298/Documents/transcriptx/docs/ROADMAP.md)
- `whispermlx` provider: Darwin-only availability checks; subprocess `whispermlx <audio> --output_dir … --language … --model … [--diarize]`; discovers `{stem}.json` (or newest post-start JSON) — [whispermlx_provider.py](file:///Users/89298/Documents/transcriptx/src/transcriptx/services/transcription/whispermlx_provider.py)
- `whisperx_docker` provider: requires host `docker` + reachable daemon; `docker run --rm` with optional `--gpus all` when `device=cuda`; mounts audio parent RO and output RW; passes WhisperX CLI flags including diarize/min/max speakers — [whisperx_docker_provider.py](file:///Users/89298/Documents/transcriptx/src/transcriptx/services/transcription/whisperx_docker_provider.py)
- Docs lock topology: engines stay out of `transcriptx:latest`; Compose analysis does not mount Docker socket; Run in app works when Streamlit sees host binaries (native Mac) and usually fails inside Compose GUI — [transcription.md](file:///Users/89298/Documents/transcriptx/docs/runtime/transcription.md); [stt-stacks README](file:///Users/89298/Documents/transcriptx/docs/recipes/stt-stacks/README.md); [ARCHITECTURE.md](file:///Users/89298/Documents/transcriptx/docs/ARCHITECTURE.md)
- Theme H shipped slices H1–H4; deferred H5+ = NVIDIA Parakeet/Canary, YouTube URL ingest, HTTP STT sidecar; H6 = streaming (opt-in cloud only if ever); non-goal: in-process NeMo in analysis image — [ROADMAP.md Theme H](file:///Users/89298/Documents/transcriptx/docs/ROADMAP.md)
- Theme K ships copyable POSIX + PowerShell command generation for whispermlx / whispermlx-missing / WhisperX Docker / Whisper-WebUI, plus saved presets under `.transcriptx/profiles/stt_commands/` (no `HF_TOKEN` in presets) — [ROADMAP.md Theme K](file:///Users/89298/Documents/transcriptx/docs/ROADMAP.md); [command_gen.py](file:///Users/89298/Documents/transcriptx/src/transcriptx/services/transcription/command_gen.py)

### Inferences
- A realistic **host provider** plug-in must: (1) implement the Protocol, (2) emit a discoverable WhisperX-shaped JSON (or a path that Import already accepts), (3) expose honest `is_available` checks for the host OS/toolchain, (4) stay out-of-process relative to the analysis image.
- Extending Theme H beyond Whisper means a new registry entry + options surface, not a silent dependency pull into `transcriptx-web`.
- Theme K is the correct bridge for engines that are CLI/Docker-ready but not worth a first-class provider yet.

### Gaps
- Exact on-disk JSON schema produced by the third-party `whispermlx` binary is not documented in-repo beyond “WhisperX / whispermlx JSON”; adapter tests use WhisperX fixtures as the contract — [word_level.json](file:///Users/89298/Documents/transcriptx/tests/fixtures/transcripts/whisperx/word_level.json)
- No in-repo HTTP STT sidecar interface sketch beyond the H5+ roadmap bullet.

---

## What JSON/schema does managed import expect (segments, words, speakers, timings)?

### Takeaway
Providers and host scripts write **raw engine JSON**; managed import converts that into canonical schema v1.0 (`schema_version` + `source` + `segments` with required `start`/`end`/`speaker`/`text`). The primary JSON native shape is WhisperX-compatible segments (optional word arrays with speaker/scores).

### Cited Findings
- WhisperX adapter accepts three shapes: `{"segments":[…]}`, word-level speakers on `words[]`, or bare list of segments; detection keys are segment `{start,end,text}` and word `{word,start,end}` — [whisperx_engine.py](file:///Users/89298/Documents/transcriptx/src/transcriptx/io/import_adapters/json_vendor/whisperx_engine.py)
- Fixture example (word-level + speakers): segments with float timings, text, and `words` carrying per-word speaker labels — [word_level.json](file:///Users/89298/Documents/transcriptx/tests/fixtures/transcripts/whisperx/word_level.json)
- Intermediate turn contract: `text`, optional `speaker`, optional `start`/`end`, optional `words` list — [intermediate_transcript.py](file:///Users/89298/Documents/transcriptx/src/transcriptx/io/intermediate_transcript.py)
- Canonical library document requires `schema_version`, `source` (`type`, `original_path`, `imported_at`, …), and `segments[]` each with non-empty `speaker` plus numeric `start`/`end` and string `text`; optional `words` — [transcript_schema.py](file:///Users/89298/Documents/transcriptx/src/transcriptx/io/transcript_schema.py)
- Built-in import adapters: Zoom VTT, VTT, SRT, WhisperX JSON, Sembly HTML, Otter/Fireflies/Rev plain text, generic text — [registry_builtins.py](file:///Users/89298/Documents/transcriptx/src/transcriptx/io/import_adapters/registry_builtins.py)
- Documented BYO formats also include Whisper-WebUI SRT/VTT, RiverScript, noScribe VTT/HTML/TXT, aTrain TXT/JSON (if segment-shaped), AssemblyAI/Deepgram/Otter/etc. JSON when compatible — [transcription.md](file:///Users/89298/Documents/transcriptx/docs/runtime/transcription.md); [comparison-reference.md](file:///Users/89298/Documents/transcriptx/docs/comparison-reference.md)
- Host STT writes under `…/originals/`; Import/Admit is the library gate; Import-all-from-folder refuses scanning managed `transcripts/` / `originals/` — [ROADMAP.md](file:///Users/89298/Documents/transcriptx/docs/ROADMAP.md); [stt-stacks README](file:///Users/89298/Documents/transcriptx/docs/recipes/stt-stacks/README.md)
- Word scores are normalized under a unit-interval policy during WhisperX parse (invalid/out-of-range scores dropped with warnings) — [whisperx_engine.py](file:///Users/89298/Documents/transcriptx/src/transcriptx/io/import_adapters/json_vendor/whisperx_engine.py)

### Inferences
- **Compatible with adapter (no new schema):** engines that emit WhisperX-like JSON, or already-supported SRT/VTT/TXT/HTML vendor shapes.
- **Adapter-only work (no schema change):** new vendor JSON that can map to `IntermediateTurn` (text + timings + speaker ± words).
- **Needs new schema / product decision:** timed but speakerless-only pipelines that refuse placeholder speakers; streaming partials; target-speaker-only text without segment timings; NeMo JSONL manifests that are not segment lists.

### Gaps
- Full list of vendor JSON detectors beyond WhisperX (AssemblyAI/Deepgram/Scriberr) is documented at product level but not all have dedicated engine modules in `json_vendor/` — only WhisperX is registered as a JSON vendor adapter in builtins.
- Exact aTrain JSON field names accepted “if segments have start/end/speaker/text” are not fixture-pinned in the WhisperX suite — [comparison-reference.md](file:///Users/89298/Documents/transcriptx/docs/comparison-reference.md)

---

## Which engines can emit compatible artifacts with an adapter vs need new schema?

### Takeaway
Whisper-family outputs (whispermlx, WhisperX, faster-whisper stacks that export WhisperX/SRT/VTT) fit today. NeMo Parakeet/Canary need a thin JSON↔WhisperX adapter (or Theme K + post-process). CocktailASR-1 and classic toolkits (Kaldi, DeepSpeech) do not fit the batch diarized-segment contract without substantial new product surfaces.

### Cited Findings
- **Already first-class / recipe-backed:** whispermlx + WhisperX Docker providers; Whisper-WebUI → SRT/VTT import; expected output format labelled WhisperX JSON in Transcribe Audio UI — [transcription.md](file:///Users/89298/Documents/transcriptx/docs/runtime/transcription.md); [command_gen.py](file:///Users/89298/Documents/transcriptx/src/transcriptx/services/transcription/command_gen.py); [whisperx recipe](file:///Users/89298/Documents/transcriptx/docs/recipes/whisperx/README.md)
- **Upstream apps (BYO, not providers):** Scriberr (Parakeet/Canary/Whisper-class locally), noScribe (VTT preferred), aTrain (TXT/JSON) — [comparison.md](file:///Users/89298/Documents/transcriptx/docs/comparison.md); [comparison-reference.md](file:///Users/89298/Documents/transcriptx/docs/comparison-reference.md)
- **Libraries listed as not workbenches:** OpenAI Whisper / whisper.cpp / faster-whisper; Vosk (streaming/embedded); Kaldi (research recipes); Mozilla DeepSpeech (development stopped) — [comparison-reference.md](file:///Users/89298/Documents/transcriptx/docs/comparison-reference.md)
- **Parakeet/Canary (NeMo):** Python `transcribe()` returns Hypothesis text; CLI `transcribe_speech.py` writes **JSONL manifests** (NeMo prediction format), optional timestamps; Canary v2 manifest can request `timestamp` / `diarize` prompt keys — not WhisperX `segments[]` — [NeMo ASR intro](https://docs.nvidia.com/nemo/speech/latest/asr/intro.html); [NeMo inference](https://docs.nvidia.com/nemo/speech/3.0.0/asr/inference.html); [NeMo datasets / Canary manifest](https://github.com/NVIDIA/NeMo/blob/main/docs/source/asr/datasets.rst); [transcribe_speech.py](https://github.com/NVIDIA/NeMo/blob/main/examples/asr/transcribe_speech.py)
- Roadmap forbids in-process NeMo in the analysis image; Parakeet/Canary sit in deferred H5+ as host/Docker orchestration later — [ROADMAP.md Theme H](file:///Users/89298/Documents/transcriptx/docs/ROADMAP.md)
- **Xiaomi CocktailASR-1:** target-speaker ASR SpeechLLM; API is `model(target.wav, ref_speaker.wav)` returning text (optional CoT); ~35.6 GB weights; Apache-2.0; research release 2026 — [xiaomi-cocktailasr-1 GitHub](https://github.com/xiaomi-research/xiaomi-cocktailasr-1); [HF Ease3/Xiaomi-CocktailASR-1](https://huggingface.co/Ease3/Xiaomi-CocktailASR-1); [arXiv:2609.11274](https://arxiv.org/abs/2609.11274)

### Inferences
| Engine / stack | Artifact path into TranscriptX | Effort class |
|----------------|--------------------------------|--------------|
| whispermlx / WhisperX | Native JSON → WhisperX adapter | **Zero** (shipped) |
| Whisper-WebUI / noScribe | SRT/VTT → subtitle adapters | **Zero** (shipped) |
| aTrain / Scriberr exports | TXT/VTT/JSON if shapes match | **Low** (BYO; possible small adapter) |
| faster-whisper / whisper.cpp | Export SRT/VTT or wrap to WhisperX JSON | **Low** (Theme K + thin adapter) |
| Parakeet / Canary (NeMo CLI) | JSONL/Hypothesis → WhisperX-shaped JSON converter | **Medium** (Theme K now; H5 provider later) |
| Vosk | Streaming partials / different JSON | **High** (new schema or lose timings/speakers) |
| CocktailASR-1 | Plain text for one enrolled voice; needs ref clip | **Research / product mismatch** |
| Kaldi / DeepSpeech | Custom lattices / abandoned | **Reject / defer** |

### Gaps
- Did not inspect a live Scriberr export sample to confirm whether it already emits WhisperX-shaped JSON or a private schema.
- Canary `diarize=yes` output shape vs WhisperX segment speakers was not verified against a concrete sample file (docs describe prompt keys, not TranscriptX-ready JSON).

---

## Hardware matrix: owner Mac (MLX) vs CUDA Docker vs CPU

### Takeaway
Owner Mac prefers host MLX (`whispermlx`); Linux/Windows prefer WhisperX Docker (CUDA when available, else CPU). Analysis Compose is Linux and never hosts MLX. New engines must declare which of these three lanes they occupy or they are Theme K–only.

### Cited Findings
- Preferred STT by host OS: macOS → whispermlx; Linux → WhisperX Docker; Windows → WhisperX/WebUI + PowerShell Copy command; no whispermlx on Windows/Linux — [transcription.md](file:///Users/89298/Documents/transcriptx/docs/runtime/transcription.md)
- whispermlx is Metal/MLX host binary; cannot run in Linux analysis image or via Docker Desktop GPU on Mac — [stt-stacks README](file:///Users/89298/Documents/transcriptx/docs/recipes/stt-stacks/README.md)
- WhisperX Docker provider adds `--gpus all` only when `options.device == "cuda"`; otherwise CPU docker run — [whisperx_docker_provider.py](file:///Users/89298/Documents/transcriptx/src/transcriptx/services/transcription/whisperx_docker_provider.py)
- Topologies A–E document Compose+host MLX, native GUI Run in app, Compose+WhisperX, optional WebUI, and Windows/Linux inbox without MLX — [stt-stacks README](file:///Users/89298/Documents/transcriptx/docs/recipes/stt-stacks/README.md)
- Whisper-WebUI on Apple Silicon expected CPU; prefer host whispermlx for speed — [transcription.md](file:///Users/89298/Documents/transcriptx/docs/runtime/transcription.md)
- NeMo Parakeet docs emphasize CUDA GPU inference; MPS (`allow_mps`) exists on CLI but is not a TranscriptX-supported Mac path today — [transcribe_speech.py](https://github.com/NVIDIA/NeMo/blob/main/examples/asr/transcribe_speech.py)
- CocktailASR-1 samples use `.cuda()` — [HF model card](https://huggingface.co/Ease3/Xiaomi-CocktailASR-1)

### Inferences
- **Near-term host providers** must land in an existing lane: Mac binary (like whispermlx) or host `docker run` (like WhisperX).
- Parakeet/Canary as H5 should be a **CUDA Docker (or host NeMo) provider**, not an analysis-image extra; Mac owners keep whispermlx as primary.
- CPU-only Docker engines are acceptable for Theme K / secondary Run-in-app when CUDA absent, matching WhisperX CPU mode.

### Gaps
- Owner machine’s exact GPU inventory is not in-repo; recommendations assume “Mac MLX host + optional Linux CUDA” from docs, not a measured RTFx matrix for Parakeet on the owner’s hardware.
- No TranscriptX benchmark comparing whispermlx large-v3 vs WhisperX CPU vs Parakeet TDT on shared audio.

---

## License/governance fit for local-first (align with trust docs if present)

### Takeaway
Local-first governance allows optional host downloads and gated HF tokens for diarization, but forbids silent remote STT. Candidate engines must stay opt-in, attributable, and outside the analysis image; AGPL/GPL upstream apps are fine as BYO upstreams, problematic if vendored into TranscriptX itself.

### Cited Findings
- Trust gate: no product telemetry; no remote analysis SaaS in 1.0; remote only when user enables HF/spaCy downloads, Ollama, optional rename web lookup, etc. — [trust_privacy_model_governance_1_0.md](file:///Users/89298/Documents/transcriptx/docs/dev/trust_privacy_model_governance_1_0.md)
- Theme H: no silent cloud STT; H6 streaming would be explicit API-key opt-in with documentation that audio leaves the machine — [ROADMAP.md Theme H](file:///Users/89298/Documents/transcriptx/docs/ROADMAP.md)
- Diarization requires `HF_TOKEN` in `whisperx.env` (gated pyannote); tokens never stored in command-gen presets — [transcription.md](file:///Users/89298/Documents/transcriptx/docs/runtime/transcription.md); [ROADMAP Theme K](file:///Users/89298/Documents/transcriptx/docs/ROADMAP.md)
- noScribe GPL-3.0; aTrain AGPL-3.0; Whisper-WebUI Apache-2.0 (recipe table); Amical MIT — [comparison-reference.md](file:///Users/89298/Documents/transcriptx/docs/comparison-reference.md); [whisper-webui recipe](file:///Users/89298/Documents/transcriptx/docs/recipes/whisper-webui/README.md)
- Parakeet TDT models: CC-BY-4.0, commercial/non-commercial ready — [nvidia/parakeet-tdt-0.6b-v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3)
- CocktailASR-1: Apache-2.0 project license — [xiaomi-cocktailasr-1 LICENSE](https://github.com/xiaomi-research/xiaomi-cocktailasr-1)
- Trust matrix today covers analysis NLP models, not STT engines (STT is BYO/host) — [trust_privacy_model_governance_1_0.md](file:///Users/89298/Documents/transcriptx/docs/dev/trust_privacy_model_governance_1_0.md)

### Inferences
- Shipping a **host-orchestrated** Parakeet/Canary Docker recipe aligns with trust docs if: downloads are user-triggered, NOTICE/attribution for CC-BY models is documented, and nothing phones home.
- Prefer **not** to vendor AGPL interview apps; keep them as documented upstreams (current posture).
- Any future H5 provider should add STT rows to the trust/licence matrix before release (gap vs analysis models today).

### Gaps
- Canary model card licence string not re-fetched in this pass (Parakeet CC-BY-4.0 confirmed; treat Canary as “verify Hub `licence=` before ship”).
- Whether NVIDIA NeMo toolkit licence + container base images impose additional distribution constraints for a TranscriptX recipe was not audited.

---

## Recommended plug-in tiers (near-term providers / command-gen / watchlist / reject)

### Takeaway
Keep Whisper-class providers as the only Tier-1 Run-in-app surface through 1.0. Use Theme K to absorb CUDA/CPU CLIs (including a future Parakeet `docker run` snippet). Park CocktailASR-1 and streaming/target-speaker research as watchlist. Reject embedding engines into the analysis image or reviving DeepSpeech/Kaldi as product paths.

### Cited Findings
- Decision fork already chosen: **Narrow Whisper-only host orchestration**; invest in Parakeet/Canary later; do not half-ship silent cloud STT — [ROADMAP.md Theme H](file:///Users/89298/Documents/transcriptx/docs/ROADMAP.md)
- Theme K explicitly invites “further CUDA Linux / CPU CLIs as needed” beside H — [ROADMAP.md Theme K](file:///Users/89298/Documents/transcriptx/docs/ROADMAP.md)
- Command-gen tools today: `whispermlx_single`, `whispermlx_missing`, `whisperx_docker`, `whisper_webui_docker` (POSIX + PowerShell) — [command_gen.py](file:///Users/89298/Documents/transcriptx/src/transcriptx/services/transcription/command_gen.py)
- Comparison page positions Scriberr/noScribe/aTrain as upstreams, not TranscriptX substitutes; Parakeet/Canary/YouTube remain later — [comparison.md](file:///Users/89298/Documents/transcriptx/docs/comparison.md)
- CocktailASR-1 is a 2026 research TS-ASR model with ref-speaker prompting and text (not diarized batch JSON) — [arXiv:2609.11274](https://arxiv.org/abs/2609.11274); [GitHub README](https://github.com/xiaomi-research/xiaomi-cocktailasr-1)

### Inferences

#### (1) Near-term host providers (Theme H — keep / harden only)
- **whispermlx** (Mac MLX) — shipped; primary owner-Mac path.
- **WhisperX Docker** (CUDA or CPU) — shipped; primary Linux/Windows path.
- **Do not add** a third provider until Whisper path is “boring” per H5 gate (availability UX, job drain, originals→admit hygiene).

#### (2) Command-gen only (Theme K — actionable next)
Priority order for new copyable snippets / `inbox-watch --transcribe command` templates:
1. **NeMo Parakeet TDT** `docker run` or host CLI → write JSON under `originals/` via a small **WhisperX-shaped converter** (roadmap-thickening for H5 without registry work).
2. **Canary** same pattern when multilingual/AST matters; still host/Docker, not analysis image.
3. **faster-whisper / whisper.cpp** folder batch → SRT/VTT or JSON (CPU-friendly Windows/Linux when WhisperX image is heavy).
4. Optional: document **Scriberr / aTrain / noScribe** as “export then Import” presets (paths only), not subprocess providers.

#### (3) Research watchlist (including CocktailASR-1)
- **NVIDIA Parakeet / Canary** — H5+ candidate provider after Theme K converter proves admit path; CUDA Docker lane; CC-BY attribution in NOTICE/trust matrix.
- **HTTP STT sidecar** — H5+; only if host orchestration needs a long-lived daemon (not Compose analysis).
- **YouTube URL ingest** — H5+ download/transcribe; rename metadata stays Theme F.
- **Xiaomi CocktailASR-1** — interesting for enrolled-speaker / cocktail-party research; **not** a batch meeting diarization replacement; would need ref-clip UX tied to speaker profiles + timing reconstruction; 35GB+ CUDA footprint → watchlist only.
- **H6 streaming** — separate product (partials, WebSocket); local batch remains default; cloud only with explicit key.
- **Vosk** — watch for voice-note / edge scripts (G4), not Balanced corpus STT.

#### (4) Reject / defer
- **In-process NeMo / Whisper inside `transcriptx:latest`** — architecture non-goal.
- **Silent cloud STT** (AssemblyAI/Deepgram as default) — rejected; cloud remains BYO export import or future explicit opt-in.
- **Mozilla DeepSpeech** — upstream stopped; prefer Whisper-class/Vosk — [comparison-reference.md](file:///Users/89298/Documents/transcriptx/docs/comparison-reference.md)
- **Kaldi-as-product** — research toolkit, steep ops curve; no GUI fit.
- **Amical / dictation apps** — wrong job (focus-app dictation), weak timed handoff — [comparison-reference.md](file:///Users/89298/Documents/transcriptx/docs/comparison-reference.md)
- **Meeting bots / auto-join Zoom** — Theme H non-goal.

### Roadmap-thickening recommendations (actionable)
1. **Theme K slice:** add a Parakeet/Canary command-gen tool enum + converter script that emits `{segments:[{start,end,text,speaker?}]}` into `originals/`; keep Import as gate.
2. **H5 entry criteria:** converter golden fixtures + CUDA Docker recipe + trust-matrix row + Mac honesty (“use whispermlx”).
3. **Do not** open CocktailASR-1 or streaming work before H5 converter/provider path exists.
4. Keep **Scriberr/noScribe/aTrain** documented as upstreams; invest adapter time only if a recurring export shape fails Import.

### Gaps
- No owner decision recorded on whether Parakeet should ever become a registered `TranscriptionProvider` vs stay Theme K forever.
- No measured WER/RTFx or operator complexity comparison on TranscriptX corpus audio for the shortlist.
