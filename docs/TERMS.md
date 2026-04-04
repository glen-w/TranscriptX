Type: CONTRACT
Authority: runtime/STORAGE.md + run_outcome_contract.md + contracts/output-contract-v1.md + public_surfaces.md

# TranscriptX terminology index (non-authoritative)

This document is an **index of terms only**. It aggregates terminology from the authoritative CONTRACT documents and points back to them.

- It **must not** introduce new semantics or rules.
- If any wording here appears to conflict with a CONTRACT document, the **CONTRACT document wins**.

Where you need the actual definition or invariant, always read the linked CONTRACT section.

## Terms and authorities

- **Canonical transcript**  
  - See storage contract: `docs/runtime/STORAGE.md` (canonical transcript validation).  
  - See ingestion guide (non-authoritative detail): `docs/runtime/transcription.md`.

- **Managed transcript**  
  - See storage contract: `docs/runtime/STORAGE.md` (managed transcript and metadata layout).

- **Library-valid transcript**  
  - See storage contract: `docs/runtime/STORAGE.md` (canonical + sidecars + archival/original linkage).

- **Sidecar**  
  - See storage contract: `docs/runtime/STORAGE.md` (metadata mirroring invariant and sidecar paths).

- **Metadata subtree**  
  - See storage contract: `docs/runtime/STORAGE.md` (metadata subtree layout and helpers).

- **Staging vs canonical storage**  
  - See storage contract: `docs/runtime/STORAGE.md` (imports/ staging semantics and canonical storage model).

- **Run outcome / execution truth**  
  - See run outcome contract: `docs/run_outcome_contract.md`.

- **Outputs and run artifacts**  
  - See output contract: `docs/contracts/output-contract-v1.md`.

- **Public surface / supported surface**  
  - See public surfaces contract: `docs/public_surfaces.md`.

This index may grow as new terms are introduced in CONTRACT docs, but each term here must always **delegate meaning** to those documents rather than redefining it.
