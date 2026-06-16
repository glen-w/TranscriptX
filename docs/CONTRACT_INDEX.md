Type: GUIDE
Authority: contracts

# Contract boundary map

Concept → Authority:

- **Storage** → `docs/runtime/STORAGE.md`
- **Run truth & statuses** → `docs/run_outcome_contract.md`
- **Core pipeline layering & lifecycle** → `docs/dev/pipeline_contracts.md`
- **Outputs & layout** → `docs/contracts/output-contract-v1.md`
- **Public surfaces & support** → `docs/public_surfaces.md`
- **Terms (index only)** → `docs/TERMS.md`

All other docs (README, guides, architecture, runtime docs) may only summarize these contracts briefly and must link back here for rules.

---

## Truth hierarchy

When interpreting a run, the system observes the following **truth hierarchy**:

1. `run_results.json` — **execution truth** (what actually happened in a run).
2. CONTRACT docs — **rules** (what must be true about structure, behavior, and invariants).
3. `manifest.json` — **index** (mapping between runs, outputs, and filesystem artifacts).
4. Filesystem — **implementation artifact** (the concrete files and directories on disk).

Lower levels **must not contradict** higher levels. In any apparent conflict, higher levels are authoritative and lower levels are considered invalid or stale until corrected.

