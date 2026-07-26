Type: GUIDE
Authority: docs/PRODUCT.md

# Known limitations (1.0 programme)

Concise user-facing limits for TranscriptX **0.9.x → 1.0**. Deeper audit rows live in developer docs; this page is the single public summary. Do not duplicate claims elsewhere — **link here**.

## Experimental analyses

Some modules are experimental classifiers or heuristics (notably **contextual emotion** and **fine-grained emotion**). They are kept off Balanced defaults; opt in via Thorough / Custom presets if you want them. Outputs are not definitive affect labels.

## Optional BERTopic and compiled dependencies

BERTopic requires the optional `[bertopic]` (or `[full]`) stack (`bertopic` / `hdbscan` / `umap-learn`). Core installs deliberately omit that stack so clean installs are not blocked by `umap-learn` → `numba` → `llvmlite` source builds on some hosts (especially certain **macOS arm64** environments without usable wheels).

Without the extra, the module stays listed and runs report a stable `missing_extra:bertopic` / `broken_extra:bertopic` skip — the pipeline continues. Docker / `requirements.txt` images still ship the fuller stack where the image build succeeds.

See [bertopic_optional_module.md](dev/bertopic_optional_module.md) and the [install verification matrix](runtime/install_verification_matrix.md).

## Large library / performance measurements

Documented corpus sizes and a measurement recipe ship in developer performance envelopes. **Large-library UI soak** may still be pending on release hardware — treat as soft-cut until measured or explicitly accepted as a known limitation in release evidence.

## Voice identity privacy

Voice fingerprint / speaker-match features are identity-sensitive. Read the in-app voice privacy notice before enabling. Local processing does not remove the sensitivity of biometric-like embeddings stored on disk.

## Stochastic Local AI output

Optional Ollama / Local AI modules are stochastic. Re-runs can differ. Artifacts carry model identity fields where available; treat Local AI text as assistive, not ground truth. Principal surfaces label Local AI vs deterministic summaries.

## Model / dataset / licence facts (`owner-verify`)

Some third-party model and dataset licence rows remain marked **`owner-verify`** in the trust / NOTICE drafts. Those cells are **not** legal conclusions until owner Hub-card sign-off. See [NOTICE](../NOTICE) (draft) and developer trust governance notes.

## Install honesty (Mac MPS)

Native **Apple MPS** is **supported-with-caveats**, not universally validated for every optional model. Prefer **Docker CPU** for predictable installs. If MPS initialisation or model execution fails, use `TRANSCRIPTX_FORCE_CPU=1` (documented in [installation.md](runtime/installation.md)). Do not assume every optional model runs reliably on MPS.
