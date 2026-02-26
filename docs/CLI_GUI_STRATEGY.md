# CLI / GUI Strategy (v0.1–v0.42)

This document defines TranscriptX’s positioning and boundaries for the CLI, Engine, and Web Viewer. It is the single source of truth for “who does what” and what is out of scope.

---

## Positioning (v0.1–v0.42)

TranscriptX is **CLI-first**.

- The **CLI** is the canonical execution surface.
- All transcript processing, speaker identification, module selection, and run creation occur in the CLI.
- The **Web Viewer** is strictly read-only.
- The Viewer exists to explore, browse, and structure run outputs — not to mutate or generate them.

This separation is intentional and foundational.

---

## 1. Architectural Boundary

### 1.1 Engine (Core Pipeline)

Responsible for:

- Canonical transcript handling
- Dependency resolution (DAG)
- Module execution
- Artifact writing
- Manifest generation
- Deterministic run outputs

The engine:

- Does not perform user interaction
- Does not assume UI context
- Does not depend on Streamlit or CLI

---

### 1.2 CLI (Workbench)

Responsible for:

- Interactive workflows
- Speaker identification
- Preset selection
- Configuration resolution
- Run orchestration
- Clear run summaries and review screens

The CLI:

- Is the only component allowed to initiate pipeline execution
- Is the only component allowed to mutate transcript metadata (e.g. speaker mapping)
- May display summaries, but does not compute new analytics

CLI design goals:

- Deterministic
- Transparent (show what will run / what will be skipped)
- Minimal surprise
- Reproducible

---

### 1.3 Web Viewer (Gallery)

Responsible for:

- Browsing run directories
- Displaying artifacts
- Rendering charts
- Showing effective configuration
- Searching and filtering runs

The Viewer:

- Never creates runs
- Never edits transcripts
- Never modifies speaker mappings
- Never re-computes analysis
- Never interprets beyond manifest + artifact contents

The Viewer is a structured browser for the run contract.

---

## 2. Immediate CLI Polishing (Pre-Install Release)

### 2.1 Speaker Mapping Enhancements

- Print a “Speaker Mapping Summary” before confirmation
- Show per-speaker segment counts and duration
- Explicitly list unmapped speakers
- Display exclusions notice for unmapped speakers
- Confirm mapping persistence path

No changes to storage format.

---

### 2.2 Review Before Run

Before pipeline execution:

- Show transcript identifier
- Show output directory
- List modules that will run
- List modules that will be skipped with reason

No additional prompts required.

---

### 2.3 Post-Run Compact Summary

After run:

- Run status (success / partial / failed)
- Output directory
- Modules executed
- Modules skipped
- Modules failed (short label only)
- Viewer command hint

Keep existing detailed summary intact.

---

## 3. Web Viewer Guardrails

The following are explicitly **out of scope** for v0.1:

- Creating new analysis runs
- Editing transcripts
- Editing speaker mappings
- Modifying configuration
- Re-running modules
- Derived analytics beyond stored artifacts

The Viewer reads:

- `manifest.json`
- `run_config_effective.json`
- Artifact files written by modules

Nothing else.

---

## 4. Near-Term Stabilization (v0.1–v0.42)

### 4.1 Installation Hardening

- Clean packaging
- Stable dependency resolution
- Clear setup instructions
- Optional dependency gating

### 4.2 Output Contract Stability

- Treat artifact structure as stable.
- Avoid renaming output folders without versioning (use versioned namespaces when introducing new layouts).
- Avoid changing manifest schema without bumping version; preserve backward compatibility or document migration.

### 4.3 CLI UX Refinement

- Improve clarity
- Improve deterministic review screens
- Avoid feature creep

---

## 5. Later Evolution (v0.3+)

Possible expansions (not committed):

- Run comparison view in Web Viewer
- Improved filtering/search across runs
- Advanced speaker curation interface (optional GUI)
- Group-level visual analytics

These must not compromise:

- Deterministic engine
- CLI as canonical execution surface
- Stable artifact contract

---

## 6. Non-Goals (v0.1)

- Plugin system
- Hosted multi-user platform
- Full GUI replacement of CLI
- Real-time collaborative editing
- Background task orchestration server

TranscriptX remains:

- Local-first
- Deterministic
- File-based
- Engine-driven

---

## 7. Guiding Principle

**Creation** happens in the workbench (CLI).

**Exploration** happens in the gallery (Web Viewer).

The engine remains the single source of analytical truth.
