Type: GUIDE
Authority: contracts

# Contract boundary map

**Product definition (non-contract):** [PRODUCT.md](PRODUCT.md)  
**Support / public surfaces:** [public_surfaces.md](public_surfaces.md)  
**Schema epoch policy:** planned under Phase 0B stubs / 0.9.1 — see [pre_release_roadmap_1_0.md](dev/pre_release_roadmap_1_0.md)

Concept → Authority:

- **Storage** → `docs/runtime/STORAGE.md`
- **Speaker profiles (longitudinal)** → `docs/contracts/speaker_profiles_v1.md`
- **Speaker profiles voice phase (local matching)** → `docs/contracts/speaker_profiles_voice_v1.md`
- **Speaker voice match index gate (Stage 9)** → `docs/dev/speaker_voice_match_index_gate.md`
- **Speaker profiles reference-env index gate** → `docs/dev/speaker_profiles_reference_env_index_gate.md`
- **Run truth & statuses** → `docs/run_outcome_contract.md`
- **Core pipeline layering & lifecycle** → `docs/dev/pipeline_contracts.md`
- **Outputs & layout** → `docs/contracts/output-contract-v1.md`
- **Public surfaces & support** → `docs/public_surfaces.md`
- **Terms (index only)** → `docs/TERMS.md`
- **Local LLM modules** → `docs/runtime/llm.md`
- **Lexical diversity** → `docs/runtime/lexical_diversity.md`
- **Keyphrases (B16)** → `docs/runtime/keyphrases.md`
- **Epistemic markers (B6)** → `docs/runtime/epistemic_markers.md`
- **Politeness (B7)** → `docs/runtime/politeness.md`
- **Topic shift (B9)** → `docs/runtime/topic_shift.md`
- **Transcript quality / ASR confidence (B3)** → `docs/runtime/transcript_quality.md`

All other docs (README, guides, architecture, runtime docs) may only summarize these contracts briefly and must link back here for rules.

---

## Truth hierarchy (summary)

When interpreting a run, precedence is defined in **`docs/run_outcome_contract.md`** (execution truth in `run_results.json` over `manifest.json` and raw file presence). This index does not restate those rules — see that contract for allowed statuses, projection rules, and invalid combinations.
