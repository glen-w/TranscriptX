Type: PRODUCT
Authority: self

# TranscriptX Roadmap

**Current version:** see [pyproject.toml](../pyproject.toml) (package version).

**Product definition:** [PRODUCT.md](PRODUCT.md)  
**Programme plan (0.9.x → 1.0):** [pre_release_roadmap_1_0.md](dev/pre_release_roadmap_1_0.md)  
**Decision foundation:** [stocktake_2026-07-17.md](dev/stocktake_2026-07-17.md)

**North star:** a credible **1.0** local-first transcript analysis workbench governed by release evidence and explicit severity rules — not feature count or fixed patch assignments.

> **Status legend:** [ ] planned · [x] done · [~] in progress

---

## Current state

- Streamlit GUI + typed Python API; managed import; file-backed storage/sidecars
- Broad analysis module set (language, speakers, interactions, emotion, voice, groups, optional Ollama)
- Contracts for storage, run outcomes, outputs, and public surfaces
- Package on a **0.9.x** stabilisation track toward 1.0

Install honesty: runtime markers are **`core` | `full`** only. Transcription remains external, with command-generation handoff planned for the 0.9.x programme.

---

## 0.9.x programme (flexible themes)

Prefer thematic workstreams over fixed patch IDs. Cut releases around coherent, tested increments.

| Theme | Focus | Status |
|-------|--------|--------|
| Pre-pre-release | Stabilisation ahead of the 1.0 programme | **0.9.0** shipped |
| Hygiene + product docs | Phase 0A/0B inventories, archive, PRODUCT/README/ROADMAP | **0.9.1** shipped |
| Planning stubs + schema inventory | Phase 0B stubs; schema-epoch inventory signed off (integer `1`) | **0.9.2** (this cut) |
| Schema epoch | Public schema epoch + compatibility removal; data-epoch transition UX; module-id hygiene | next 0.9.x |
| Install + transcription | Install-profile audit; Transcribe command generation; corpus docs | later 0.9.x |
| Modes + demo | Guided / Full controls v1; demo project load/remove | later 0.9.x |
| Harden + public surfaces | Quality audit; performance envelopes; trust/privacy/model gate; hosted docs + modest website; a11y | later 0.9.x |

**Module freeze:** no new analysis modules in 0.9.x unless required to complete or repair the 1.0 journey. Backlog: [analysis_module_backlog_2026-07-17.md](dev/analysis_module_backlog_2026-07-17.md).

---

## 1.0 gate

Mandatory themes (detail in the programme plan):

- Unfamiliar-user clean-room validation — [unfamiliar_user_validation_1_0.md](dev/unfamiliar_user_validation_1_0.md)
- Release severity triage — [release_severity_triage_1_0.md](dev/release_severity_triage_1_0.md)
- Performance/resource envelopes — [performance_envelopes_1_0.md](dev/performance_envelopes_1_0.md)
- Trust / privacy / model-governance — [trust_privacy_model_governance_1_0.md](dev/trust_privacy_model_governance_1_0.md)
- Release ops and support — [release_ops_support_1_0.md](dev/release_ops_support_1_0.md); governance evidence on an exact clean commit
- Schema epoch inventory (before reset) — [schema_epoch_inventory.md](dev/schema_epoch_inventory.md)
- Usable hosted documentation and a credible public landing (may be modest)

Not required: every backlog feature, PyPI, hosted SaaS, built-in transcription, highly polished website.

---

## 1.1 – 1.x

- Elaborate guided coach-mark tour (if needed)
- Large bundled completed demo runs (if risky at 1.0)
- Archive taxonomy refinements; aesthetic polish
- Specialist convenience and non-supported configurations
- **Transcript tagging** — library visibility / kind labels so users can surface certain transcripts (e.g. `meeting`, `voice note`, `lone speaker` for one-sided phone recordings). Tags are organisation metadata, not an analysis module.

  **Design before build — interaction with Groups:** tags and groups must stay distinct. Tags find/filter/surface individual transcripts; Groups are analysis cohorts for cross-session runs. Tagging must not create or imply group membership. Tags may act as **filters** in the group member picker, but must not auto-materialise a Group without an explicit user action. Decide whether “more visible” means facet filters, optional pin/favourite, or both — without overlapping Groups as the named-collection surface. Kind tags like `lone speaker` may later feed soft suitability hints (e.g. interaction modules), but must remain optional metadata, not silent default changes. Prefer transcript-local / library storage; keep tags out of group run schemas unless a deliberate filter snapshot is needed.

---

## 2.0 vision

Personal audio intelligence companion: personal recordings, voice-note workflows, deeper conversational analytics, stronger local AI — still local-first and modular.

---

## Non-near-term / deferred

- Built-in or orchestrated transcription engine
- SQLite speaker analytics as default
- Multilingual routing beyond a small reliable subset
- B4 ConvoKit-family methods as product defaults
- Mode systems that duplicate page logic
- Elaborate interactive website effects

Historical sprint dumps: [sprint_archive.md](archive/plans/sprint_archive.md) (archived).

---

## Engineering backlogs

- [analysis_module_backlog_2026-07-17.md](dev/analysis_module_backlog_2026-07-17.md)
- [DEV_INDEX.md](DEV_INDEX.md) · [archive/ARCHIVE_INDEX.md](archive/ARCHIVE_INDEX.md)
- [release_governance.md](dev/release_governance.md)
- [release_severity_triage_1_0.md](dev/release_severity_triage_1_0.md)
- Phase 0B planning stubs: [docs_architecture_1_0.md](dev/docs_architecture_1_0.md), [install_profiles_matrix.md](dev/install_profiles_matrix.md), [manual_acceptance_1_0.md](dev/manual_acceptance_1_0.md), [analysis_quality_audit.md](dev/analysis_quality_audit.md), [ui_presentation_modes.md](dev/ui_presentation_modes.md), [demo_project.md](dev/demo_project.md)
