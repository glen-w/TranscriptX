# Xiaomi CocktailASR-1 and Open-Source Target-Speaker ASR

Research timeframe: October 2026. Primary sources preferred; secondary-only claims are marked.

## What exactly did Xiaomi open-source (repos, license, deps, checkpoints)?

### Takeaway
Xiaomi released an Apache-2.0 **inference/demo GitHub repo** plus a **Hugging Face `trust_remote_code` checkpoint** (`Ease3/Xiaomi-CocktailASR-1`, ~35.6 GB `pytorch_model.bin`) that packages a D2V2-style 0.6B audio encoder, adapter, and Qwen3-8B LLM; runtime deps are officially `torch`, `torchaudio`, `transformers`, and `soundfile`.

### Cited Findings
- Official GitHub repo: [xiaomi-research/xiaomi-cocktailasr-1](https://github.com/xiaomi-research/xiaomi-cocktailasr-1) — Apache License 2.0; contains README (zh/en), `tools/test_batch_scp.py`, `demo/` sample audio; **does not ship model `.py` weights** (loaded from HF via `trust_remote_code`). — [GitHub README_en.md](https://raw.githubusercontent.com/xiaomi-research/xiaomi-cocktailasr-1/main/README_en.md); [LICENSE](https://raw.githubusercontent.com/xiaomi-research/xiaomi-cocktailasr-1/main/LICENSE) (Copyright 2026 Xiaomi Corporation)
- Hugging Face checkpoint: [Ease3/Xiaomi-CocktailASR-1](https://huggingface.co/Ease3/Xiaomi-CocktailASR-1) — MicAsr custom code (`configuration_mic_asr.py`, `modeling_mic_asr.py`, `feature_extraction_mic_asr.py`), `d2v2_config.json`, tokenizer files, single `pytorch_model.bin`. — [HF model card](https://huggingface.co/Ease3/Xiaomi-CocktailASR-1); [GitHub README_en.md](https://raw.githubusercontent.com/xiaomi-research/xiaomi-cocktailasr-1/main/README_en.md)
- Checkpoint size on HF file browser: `pytorch_model.bin` reported as **35.6 GB**. — [HF pytorch_model.bin](https://huggingface.co/Ease3/Xiaomi-CocktailASR-1/blob/main/pytorch_model.bin)
- Install line from primary docs: `pip install torch torchaudio transformers soundfile`. — [GitHub README_en.md](https://raw.githubusercontent.com/xiaomi-research/xiaomi-cocktailasr-1/main/README_en.md); [HF model card](https://huggingface.co/Ease3/Xiaomi-CocktailASR-1)
- Load pattern: `AutoModel.from_pretrained("Ease3/Xiaomi-CocktailASR-1", trust_remote_code=True, torch_dtype="bfloat16").cuda().eval()`. — [GitHub README_en.md](https://raw.githubusercontent.com/xiaomi-research/xiaomi-cocktailasr-1/main/README_en.md)
- README model table labels LLM size as **8B**. — [GitHub README_en.md](https://raw.githubusercontent.com/xiaomi-research/xiaomi-cocktailasr-1/main/README_en.md)
- Technical report architecture: Audio Encoder (~**0.6B**, Data2Vec2-derived, 1280-dim frames) → lightweight linear Adapter → **Qwen3-8B** LLM backbone; encoder uses FBank front-end instead of raw waveform. — [arXiv:2609.11274 HTML](https://arxiv.org/html/2609.11274)
- Paper abstract/title: Xiaomi-CocktailASR-1 is an LLM-based end-to-end **TS-ASR** system using reference speech as voiceprint prompt, **without speech separation**. — [arXiv:2609.11274](https://arxiv.org/abs/2609.11274)
- Secondary aggregator (aiinnovatortech) largely restates GitHub/paper claims (SOTA numbers, Apache 2.0, deps); treat as unverified for anything not cross-checked above. — [aiinnovatortech article](https://aiinnovatortech.com/latest-ai-news/xiaomi-cocktailasr-1-speech-recognition) (**secondary**)
- Secondary “AI Tools Directory” page claims **≥16 GB VRAM**, Python ≥3.8, transformers ≥4.40, “~8.6B params”; **not stated in Xiaomi GitHub/HF primary docs reviewed**. — [ai-all.info page](https://www.ai-all.info/en/ai-models/xiaomi-cocktailasr-1) (**secondary-only**)

### Inferences
- Open-source surface is **weights + custom HF modeling code + thin inference tooling**, not a full training framework; reproduction of the reported ~1M-hour multi-stage training pipeline is not part of the OSS release.
- The HF org slug `Ease3` (not `xiaomi`) is the published download ID; GitHub explicitly points there — operators should treat `Ease3/Xiaomi-CocktailASR-1` as the canonical checkpoint ID while noting the non-Xiaomi-branded namespace for supply-chain review (`trust_remote_code=True` executes remote Python).

### Gaps
- Exact pinned versions of torch/transformers/CUDA were not published in the primary README/HF card.
- Primary sources do not publish an official VRAM/minimum-GPU matrix (16 GB is secondary-only).
- Whether training code, CoT template generators, or CAM++ labeling pipelines used in the paper are open-sourced was not found in the GitHub tree description.

## How does target-speaker ASR change the product contract vs classic Whisper+diarization?

### Takeaway
TS-ASR **locks onto one enrolled speaker and discards others** (returning empty text if that speaker is absent), whereas Whisper+pyannote-style pipelines produce **multi-speaker, time-aligned, anonymously labeled** transcripts — a fundamentally different contract for a workbench that assumes diarized multi-speaker JSON.

### Cited Findings
- Product behavior (primary): given `ref` + mixed/single `target`, model **transcribes only the target speaker**; concatenation `ref + 1s silence + target` is done **inside** the model. — [GitHub README_en.md](https://raw.githubusercontent.com/xiaomi-research/xiaomi-cocktailasr-1/main/README_en.md)
- Negative samples: if reference speaker is **absent**, output is **empty string `""`**; no special API flag. — [GitHub README_en.md](https://raw.githubusercontent.com/xiaomi-research/xiaomi-cocktailasr-1/main/README_en.md); [arXiv:2609.11274](https://arxiv.org/html/2609.11274)
- Paper contrasts **MT-ASR** (transcribe all speakers, often FIFO with special tokens, **no speaker identity association**) vs **TS-ASR** (use reference to selectively transcribe target, suppress others). — [arXiv:2609.11274 §1](https://arxiv.org/html/2609.11274)
- Paper positions classic cascade as TSE (target speaker extraction) + ASR with error accumulation; CocktailASR is end-to-end without explicit separation. — [arXiv:2609.11274 §1](https://arxiv.org/html/2609.11274)
- Classic FunASR/blog framing of the competing contract: pyannote diarization + Whisper, then align timelines → per-sentence speaker IDs + timestamps. — [FunASR diarization blog](https://www.funasr.com/en/blog/funasr-speaker-diarization.html)
- FunASR speaker-aware file path returns `sentence_info` with `start`/`end`/`spk`/`sentence` (anonymous indices within a recording, **not** enrolled-speaker ID). — [FunASR GitHub](https://github.com/modelscope/FunASR/); [FunASR diarization blog](https://www.funasr.com/en/blog/funasr-speaker-diarization.html)
- pyannote speaker-diarization pipeline yields who-spoke-when segments (optionally with `num_speakers` / min/max bounds). — [pyannote/speaker-diarization](https://huggingface.co/pyannote/speaker-diarization)
- CocktailASR standard API returns a **text string** (not timed segments); CoT mode wraps reasoning/answer tags. — [GitHub README_en.md](https://raw.githubusercontent.com/xiaomi-research/xiaomi-cocktailasr-1/main/README_en.md); [HF model card](https://huggingface.co/Ease3/Xiaomi-CocktailASR-1)

### Inferences
| Contract dimension | Whisper + diarization (classic) | CocktailASR / TS-ASR |
|---|---|---|
| Speakers in output | All (SPEAKER_00…) | One enrolled speaker only |
| Enrollment | None (clustering) | Required reference clip |
| Missing target | Still transcripts others | Empty output (rejection) |
| Timestamps | Typical (segment-level) | Not in published API |
| Multi-speaker analytics | Compatible | Breaks unless N passes with N refs |
| Overlap handling | Often weak / cascade errors | Trained for cocktail mixtures |

- For TranscriptX-style **multi-speaker diarized JSON**, CocktailASR is a **different plugin**: “filter to this person’s words,” not “label everyone.” Mapping would require either (a) one call per known speaker with enrollment audio, stitching texts without shared timing, or (b) keeping diarization as the primary path and treating TS-ASR as an optional focus mode.

### Gaps
- No primary documentation of word/segment timestamps, speaker turn boundaries, or RTTM/JSON export from CocktailASR.
- No official guidance on multi-enrollment “call once per speaker” workflows for full-meeting reconstruction.

## Architecture, reference-voiceprint workflow, CoT tags, negative rejection, benchmarks

### Takeaway
Architecture is **concatenated voiceprint prompt → SSL audio encoder → adapter → Qwen3-8B**; training used ~400k h multi-speaker + ~600k h single-speaker + ~10k h negatives, with optional CoT tags reporting speaker count/gender/similarity; reported WERs beat prior TS-ASR on LibriMix/LibriSpeechMix/AMI/AliMeeting while keeping single-speaker WER near Qwen3-ASR.

### Cited Findings

#### Architecture & input protocol
- Input organization: **reference speech + 1 second silence + mixed speech**. Reference durations in training randomly sampled **1–4 seconds**. — [arXiv:2609.11274 §2.1](https://arxiv.org/html/2609.11274)
- Encoder treats reference as conditional prompt to enhance target speaker representations and suppress interferers; no separate speaker encoder. — [arXiv:2609.11274 §2.2](https://arxiv.org/html/2609.11274)
- Inference accepts path / `numpy.ndarray` / `torch.Tensor`; **16 kHz mono** (auto-resample otherwise). — [GitHub README_en.md](https://raw.githubusercontent.com/xiaomi-research/xiaomi-cocktailasr-1/main/README_en.md)
- Standard prompt (documented): “Based on the reference speech at the start, only transcribe the target speaker's speech into text.” — [GitHub README_en.md](https://raw.githubusercontent.com/xiaomi-research/xiaomi-cocktailasr-1/main/README_en.md)

#### Negative-sample rejection
- Trained by concatenating **mismatched** references; rejection internalized in weights (no inference threshold). ~**10,000 hours** negative data. — [arXiv:2609.11274 §3.1.3, §3.2](https://arxiv.org/html/2609.11274)
- Rejection Rate (RR): LibriSpeech Neg **79.59%**, Aishell Neg **75.35%**, Chinese in-house Neg **68.54%**; Qwen3-ASR / StepAudio RR **0%**. — [arXiv:2609.11274 Table 4](https://arxiv.org/html/2609.11274); [GitHub README_en.md](https://raw.githubusercontent.com/xiaomi-research/xiaomi-cocktailasr-1/main/README_en.md)
- False Rejection Rate on positive single-speaker sets remains low (e.g. LibriSpeech FRR **0.36%**). — [arXiv:2609.11274 Table 3](https://arxiv.org/html/2609.11274)

#### Chain-of-Thought
- CoT mode (`cot=True`): reasoning in `<think>…</think>`, final transcript in `<answer>…</answer>`. — [HF model card](https://huggingface.co/Ease3/Xiaomi-CocktailASR-1); [GitHub README_en.md](https://raw.githubusercontent.com/xiaomi-research/xiaomi-cocktailasr-1/main/README_en.md)
- CoT content includes **speaker count**, each speaker’s **gender**, and **voiceprint similarity** levels vs reference; similarity levels 1–5 from CAM++ cosine similarity quantization; if all similarities below threshold **3**, treat as absent → empty answer. — [arXiv:2609.11274 §3.1.4 / CoT Data](https://arxiv.org/html/2609.11274)
- CoT vs standard WER deltas are small but consistent (e.g. LibriMix 2mix 4.11 → **3.87**). — [arXiv:2609.11274 Table 5](https://arxiv.org/html/2609.11274); [GitHub README_en.md](https://raw.githubusercontent.com/xiaomi-research/xiaomi-cocktailasr-1/main/README_en.md)

#### Training scale (paper)
- Multi-speaker TS-ASR data ~**400,000 h**; single-speaker TS-ASR ~**600,000 h**; negatives ~**10,000 h**; 4-stage pipeline (ASR base → TS-ASR base → CoT → SFT+RL). — [arXiv:2609.11274 §3](https://arxiv.org/html/2609.11274)

#### Benchmarks (primary)
| Setting | CocktailASR-1 | Notable baseline |
|---|---|---|
| LibriMix 2mix WER | **4.11** | TCP 4.84; Qwen3-ASR 68.75 |
| LibriMix 3mix WER | **12.29** | TCP 12.23; Gemini-2.5-pro 76.10 |
| LibriSpeechMix 2mix | **2.90** | CONF-TSASR 5.40 |
| LibriSpeechMix 3mix | **4.91** | CONF-TSASR 7.60 |
| AMI SDM | **21.81** | SQ-Whisper 22.0; Whisper L-v2 36.40 |
| AliMeeting Far | **20.63** | MC-TS-ASR 27.50 |
| LibriSpeech non-empty WER | **1.73** (FRR 0.36) | Qwen3-ASR-1.7b 1.87 |
| CommonVoice(zh) | **4.95** (FRR 0.73) | Qwen3-ASR 5.39 |

— [arXiv:2609.11274 Tables 1–4](https://arxiv.org/html/2609.11274); mirrored in [GitHub README_en.md](https://raw.githubusercontent.com/xiaomi-research/xiaomi-cocktailasr-1/main/README_en.md)

- Demo recognition example in README is **Chinese** text; positive/negative demo WAVs provided. — [GitHub README_en.md](https://raw.githubusercontent.com/xiaomi-research/xiaomi-cocktailasr-1/main/README_en.md)

### Inferences
- Voiceprint workflow is **audio-in-audio** (raw enrollment clip), not an explicit speaker-embedding API — simplifies UX but ties quality to enrollment SNR/length.
- CoT tags are a potential **debug/UX overlay**, not a substitute for diarization metadata; similarity levels are discrete LLM-facing tokens, not calibrated verification scores for production gating.

### Gaps
- No published latency/RTF, max audio duration, or batching memory curves in primary docs.
- Multilingual coverage beyond EN/ZH benchmarks is not systematically reported (paper focuses Libri*/AMI English and AliMeeting/WenetSpeech/CommonVoice/Aishell Chinese).
- Exact CoT XML tag spelling in raw model output should be verified at runtime (HF card shows think/answer tags; HTML fetches sometimes strip angle brackets).

## Peer models (TS-ASR, speaker-attributed ASR, multi-talker, related toolkits)

### Takeaway
CocktailASR is among the few **large open SpeechLLM TS-ASR** releases; closer OSS peers are **Whisper-conditioned TS-ASR** (DiCoW / SQ-Whisper / prompt-tuned Whisper) and **diarization+ASR toolkits** (FunASR, pyannote, SpeechBrain, ESPnet) — while **Whisper-AT is audio-event tagging, not multi-talker ASR**.

### Cited Findings

#### Target-speaker / diarization-conditioned Whisper family
- **DiCoW** (BUT): Whisper conditioned on frame-level diarization STNO masks via FDDT; can produce speaker-attributed ASR by decoding per diarized speaker; HF checkpoint [BUT-FIT/DiCoW_v3_3](https://huggingface.co/BUT-FIT/DiCoW_v3_3) (Whisper large-v3-turbo base); inference repos [BUTSpeechFIT/DiCoW](https://github.com/BUTSpeechFIT/DiCoW), training [BUTSpeechFIT/TS-ASR-Whisper](https://github.com/BUTSpeechFIT/TS-ASR-Whisper). Depends on diarization quality; SE-DiCoW adds self-enrollment. — [DiCoW_v3_3 card](https://huggingface.co/BUT-FIT/DiCoW_v3_3); [DiCoW GitHub](https://github.com/BUTSpeechFIT/DiCoW); paper [Target Speaker ASR with Whisper](https://arxiv.org/html/2409.09543v2)
- **SQ-Whisper**: speaker-querying Whisper TS-ASR; ESPnet recipes/code at `pengchengguo/espnet` `tswhisper` branch; AMI WER cited as prior SOTA vs CocktailASR’s AMI SDM 21.81 (SQ-Whisper 22.0 in CocktailASR table). — [SQ-Whisper paper](https://arxiv.org/html/2412.05589); [CocktailASR Table 2](https://arxiv.org/html/2609.11274)
- **Prompt-tuned Whisper TS-ASR**: parameter-efficient (~1% task params) extension retaining Whisper timestamps / ITN. — [arXiv:2312.08079](https://arxiv.org/html/2312.08079v2)
- **TCP**: Xiaomi-related prior CoT+RL TS-ASR work cited as previous SOTA on LibriMix (4.84 / 12.23). — [arXiv:2509.15612 via CocktailASR refs](https://arxiv.org/html/2609.11274)

#### Multi-talker / speaker-attributed (non-enrollment)
- Serialized Output Training (SOT) and speaker-attributed ASR literature cited in CocktailASR intro (Kanda et al.); these output **all speakers** with tokens/attribution rather than enrollment lock. — [arXiv:2609.11274 §1 refs](https://arxiv.org/html/2609.11274)

#### Toolkits closer to TranscriptX’s current contract
- **FunASR** (MIT toolkit; model licenses separate): `AutoModel` with VAD + ASR + punctuation + **CAM++** speaker clustering → timed sentences with anonymous `spk` IDs; Chinese-strong; CPU-capable paths exist. — [modelscope/FunASR](https://github.com/modelscope/FunASR/); [FunASR diarization blog](https://www.funasr.com/en/blog/funasr-speaker-diarization.html)
- **pyannote.audio**: industry-standard diarization pipelines (often gated HF models) feeding Whisper/other ASR. — [pyannote/speaker-diarization](https://huggingface.co/pyannote/speaker-diarization)
- **SpeechBrain** (Apache 2.0): separate **ASR** and **AMI diarization** recipes (ECAPA-TDNN + spectral clustering); not a unified enrolled TS-ASR SpeechLLM. — [speechbrain/speechbrain](https://github.com/speechbrain/speechbrain/); [AMI Diarization recipe](https://github.com/speechbrain/speechbrain/tree/develop/recipes/AMI/Diarization)
- **ESPnet**: multi-speaker / TS-Whisper research recipes (see SQ-Whisper). — [SQ-Whisper / ESPnet link](https://arxiv.org/html/2412.05589)

#### Clarification: Whisper-AT
- **Whisper-AT** adds AudioSet **audio event tagging** on frozen Whisper with &lt;1% extra compute; ASR text matches original Whisper — **not** cocktail-party / multi-talker speaker ASR. — [YuanGongND/whisper-at](https://github.com/YuanGongND/whisper-at); [Whisper-AT paper](https://arxiv.org/html/2307.03183)

### Inferences
- If TranscriptX wants **“same JSON shape, better overlap”**, DiCoW/FunASR/pyannote paths stay closer than CocktailASR.
- If TranscriptX wants **“BYO enrollment / focus this person”** (assistive listening, owner-only capture), CocktailASR’s contract matches uniquely among large OSS releases reviewed.
- DiCoW still **needs a diarizer** (relative STNO masks); CocktailASR needs a **reference clip** instead — different operational dependencies.

### Gaps
- No thorough 2026 head-to-head OSS bake-off (same hardware, same meetings) found beyond CocktailASR’s selective baselining.
- SpeechBrain “speaker-attributed end-to-end ASR” production checkpoint maturity for BYO meetings was not established beyond diarization+ASR recipes.

## Practical deployment for a local-first / BYO workbench

### Takeaway
Expect a **CUDA bfloat16 SpeechLLM** with ~**8B+0.6B** weights (~**35+ GB** download), enrollment clips on the order of **1–4 s** (training regime), internal **ref+1s silence+mix** concat, and **plain text** (optionally CoT-tagged) output — heavy for laptop BYO compared with Whisper-medium + pyannote, and mismatched to timed multi-speaker JSON without adapters.

### Cited Findings
- `.cuda().eval()` + `bfloat16` is the documented path; CPU not promoted. — [GitHub README_en.md](https://raw.githubusercontent.com/xiaomi-research/xiaomi-cocktailasr-1/main/README_en.md)
- Batch tool: TSV columns `utt_id, wav, text, ref_wav, ref_id` → `tools/test_batch_scp.py` (`--cot` optional). — [GitHub README_en.md](https://raw.githubusercontent.com/xiaomi-research/xiaomi-cocktailasr-1/main/README_en.md)
- HF download volume: **35.6 GB** single bin. — [HF file page](https://huggingface.co/Ease3/Xiaomi-CocktailASR-1/blob/main/pytorch_model.bin)
- Reference length guidance from paper training: **1–4 seconds**. — [arXiv:2609.11274 §2.1](https://arxiv.org/html/2609.11274)
- Secondary deploy claim: NVIDIA GPU, **≥16 GB VRAM**, Python ≥3.8. — [ai-all.info](https://www.ai-all.info/en/ai-models/xiaomi-cocktailasr-1) (**secondary-only**)
- Apache 2.0 allows commercial use with attribution; GitHub LICENSE copyright Xiaomi 2026. — [LICENSE](https://raw.githubusercontent.com/xiaomi-research/xiaomi-cocktailasr-1/main/LICENSE)
- `trust_remote_code=True` required for custom MicAsr classes. — [HF model card](https://huggingface.co/Ease3/Xiaomi-CocktailASR-1)

### Inferences
- Disk/RAM footprint alone makes CocktailASR a **optional GPU plugin**, not a default path beside lighter Whisper/FunASR stacks already common in local transcription apps.
- Output adapter for TranscriptX would need to invent timestamps (e.g. align text to forced alignment / VAD) and speaker fields (constant enrolled ID) — non-trivial and lossy.
- Security posture: remote code execution from HF + very large binary argues for **hash pinning / local mirror** before enabling in a trusted workbench.

### Gaps
- No primary quantization (INT8/GGUF), Apple Silicon, or multi-GPU sharding guide found.
- Max utterance length / chunking strategy for hour-long meetings not documented — critical for workbench integration.

## Risks and fit for TranscriptX (diarized multi-speaker JSON assumption)

### Takeaway
CocktailASR is a **poor drop-in** for TranscriptX’s assumed multi-speaker diarized JSON (missing speaker labels, no multi-speaker analytics, no timings), but a **plausible optional “focus speaker” backend** if the product adds enrollment UX; main risks are **contract mismatch**, **hardware weight**, **EN/ZH-centric evidence**, and **early OSS maturity** (2026 release, `trust_remote_code`, HF under `Ease3`).

### Cited Findings
- Output is target-only text / empty / CoT-wrapped text — not multi-speaker labeled segments. — [GitHub README_en.md](https://raw.githubusercontent.com/xiaomi-research/xiaomi-cocktailasr-1/main/README_en.md)
- Paper explicitly says MT-ASR limitations include inability to associate transcriptions with **specific speaker identities**; TS-ASR solves a different goal. — [arXiv:2609.11274 §1](https://arxiv.org/html/2609.11274)
- Benchmarks emphasize Chinese meeting (AliMeeting) and English Libri/AMI sets; demo transcript is Chinese. — [arXiv:2609.11274](https://arxiv.org/html/2609.11274); [GitHub README_en.md](https://raw.githubusercontent.com/xiaomi-research/xiaomi-cocktailasr-1/main/README_en.md)
- Repo creation / paper timing: GitHub created **2026-07-31** (from search metadata); arXiv submitted **10 Sep 2026**. — [GitHub repo](https://github.com/xiaomi-research/xiaomi-cocktailasr-1); [arXiv abs](https://arxiv.org/abs/2609.11274)
- Peer paths that preserve multi-speaker JSON: FunASR CAM++ pipeline; pyannote+Whisper; DiCoW speaker-attributed decode. — [FunASR](https://github.com/modelscope/FunASR/); [DiCoW](https://github.com/BUTSpeechFIT/DiCoW)
- Rejection imperfect: RR mid-60s–high-70s% → some false accepts of interferers; FRR small but non-zero → occasional empty positives. — [arXiv:2609.11274 Tables 3–4](https://arxiv.org/html/2609.11274)

### Inferences
**Fit matrix (for local-first transcript workbench):**
- Keep as primary ASR+diarization replacement? **No** — breaks multi-speaker analysis modules.
- Optional plugin (“transcribe only User A given enrollment”)? **Yes, with adapter** — needs enrollment management, empty-output handling, and synthetic segment schema.
- Overlap/cocktail robustness research baseline? **Yes** — strong published TS-WER vs general LALMs.
- Chinese-first meeting focus? **Relatively strong evidence** on AliMeeting; English AMI also reported; other languages under-documented.

**Compared to classic Whisper+diarization for TranscriptX goals:**
- Whisper+diarization / FunASR: better **schema compatibility**, lighter deps, anonymous speakers, timestamps.
- CocktailASR: better **enrolled target extraction under overlap**, built-in **reject-if-absent**, explainable CoT — at cost of schema + GPU mass.

### Gaps
- Community adoption metrics beyond HF “downloads last month” snapshots were not systematically tracked for this note.
- No independent third-party reproduction of Xiaomi’s SOTA tables found as of this research pass (results rely on authors’ report + README mirror).
- TranscriptX-specific JSON schema field inventory was not re-audited in-repo for this note; contract risk assessment is based on the stated “multi-speaker diarized JSON” assumption in the research brief.

---

## Source index (primary vs secondary)

| Source | Role |
|---|---|
| [github.com/xiaomi-research/xiaomi-cocktailasr-1](https://github.com/xiaomi-research/xiaomi-cocktailasr-1) / [README_en.md](https://raw.githubusercontent.com/xiaomi-research/xiaomi-cocktailasr-1/main/README_en.md) | Primary OSS usage, license pointer, metrics mirror |
| [LICENSE](https://raw.githubusercontent.com/xiaomi-research/xiaomi-cocktailasr-1/main/LICENSE) | Primary Apache 2.0 |
| [huggingface.co/Ease3/Xiaomi-CocktailASR-1](https://huggingface.co/Ease3/Xiaomi-CocktailASR-1) | Primary checkpoint / API |
| [arXiv:2609.11274](https://arxiv.org/abs/2609.11274) | Primary architecture, training, benchmarks |
| [BUT-FIT/DiCoW_v3_3](https://huggingface.co/BUT-FIT/DiCoW_v3_3), [BUTSpeechFIT/DiCoW](https://github.com/BUTSpeechFIT/DiCoW) | Primary peer TS-ASR |
| [FunASR](https://github.com/modelscope/FunASR/), [pyannote](https://huggingface.co/pyannote/speaker-diarization), [SpeechBrain](https://github.com/speechbrain/speechbrain/), [Whisper-AT](https://github.com/YuanGongND/whisper-at) | Primary peer / contrast |
| [aiinnovatortech article](https://aiinnovatortech.com/latest-ai-news/xiaomi-cocktailasr-1-speech-recognition) | Secondary news rewrite |
| [ai-all.info CocktailASR page](https://www.ai-all.info/en/ai-models/xiaomi-cocktailasr-1) | Secondary (VRAM/version extras) |
