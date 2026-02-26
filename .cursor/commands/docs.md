Update project documentation to reflect the current codebase, CLI behavior, and workflows.
Run from the workspace root.

Skip any step requiring network access (e.g. publishing a docs site) unless explicitly requested.
After completion, summarize what was updated.

This is a documentation-only pass. The codebase is the source of truth.

---

## Overall Objective

Produce collaboration-ready documentation that:

- Accurately reflects the current CLI, flags, workflows, and architecture
- Separates high-level orientation (README) from detailed reference (docs/)
- Prevents drift between --help output and CLI documentation
- Is structured for three audiences:
  1. Power user (install + run via pip or Docker/Compose)
  2. Advanced user (understanding workflows and outputs)
  3. Contributor (architecture and extension points)

Documentation must remain:

- Plain Markdown
- Cross-linked with relative links
- Version-controlled in-repo
- Based strictly on current code behavior

---

## Phase 0 — Codebase & CLI Inventory (Required First)

Before editing documentation:

1. Identify the CLI framework and entrypoint (Typer/Click/Argparse/etc).
2. Generate and inspect:
   - `transcriptx --help`
   - `transcriptx <each top-level command> --help`
   - One level of subcommands where relevant.
3. Extract the full command tree.
4. Identify:
   - Main workflows (analysis, transcription, wav processing, database, artifacts, etc.)
   - Config handling (env vars, settings command, config files)
   - Docker/Compose entrypoints and volume expectations
   - Module layout under src/
   - Pipeline structure and module contracts
5. Identify any deprecated or removed commands referenced in existing docs.

Produce a short Findings Summary (can remain internal or included in final summary) that lists:

- Full command tree
- Primary workflows
- Configuration surface
- Any mismatches already observed between docs and code

Do not modify documentation before completing this inventory.

---

## 1. README

README must remain the high-level entry point.

### Installation

- Ensure installation instructions are accurate.
- Verify pip/venv instructions match actual package structure.
- Verify Docker/Compose instructions reflect actual compose files and image names.
- Remove outdated install paths or deprecated setup steps.

### CLI Usage

- Ensure high-level CLI examples reflect real commands and flags.
- Do NOT list every subcommand.
- Provide 1–3 "golden path" workflows.
- Link to full CLI reference in docs/CLI.md.

### Docker

- Confirm compose file names and services.
- Confirm volume paths and expected input/output directories.
- Remove references to unused Dockerfiles or legacy images.

### Deprecated Features

- Remove references to deleted commands, modules, or workflows.
- Remove obsolete flags or examples.

### Version

- Ensure version number matches current package version if displayed.

---

## 2. CLI & Commands

Create or update docs/CLI.md.

### Coverage

- Document all top-level commands.
- Document significant subcommands.
- Organize by command group if needed (e.g. analysis, wav processing, database).

### Flags and Options

- Flags and options must match current --help output exactly.
- Do not invent flags.
- Do not document internal-only parameters unless user-facing.

### Examples

- Provide minimal but accurate examples.
- Include both simple and slightly advanced examples where useful.
- Ensure every example command is runnable based on current CLI structure.

If useful, organize as:

- Command
- Description
- Usage
- Key options
- Examples

---

## 3. Architecture & Structure

Create or update:

- docs/ARCHITECTURE.md
- docs/WORKFLOWS.md
- docs/CONTRIBUTING.md (if missing)

### Module Descriptions

- Ensure module descriptions reflect actual src/ layout.
- Document stable module contracts (not every internal function).
- Reflect current pipeline structure (DAG, modules, outputs).

### Removed Components

- Remove references to deleted or refactored components.
- Remove stale directory references.

### Paths

- Ensure all file paths reflect current structure.
- Update src/ paths if reorganized.
- Update any changed Docker paths.

---

## Drift Control Strategy (Required)

Define a sustainable anti-drift approach:

- CLI flags and options → Source of truth = --help
- Docker behavior → Source of truth = compose files
- Architecture → Source of truth = current src/ layout

Add a short Documentation Sync Checklist to docs/CONTRIBUTING.md or RELEASE.md, including:

- Regenerate and review --help output
- Verify README examples
- Verify Docker examples
- Confirm no deleted commands are referenced
- Confirm version consistency

Keep this lightweight and manual unless a small local helper script is clearly justified.

---

## Execution Rules

- Documentation-only pass (no code changes).
- No speculative or future features.
- No network access.
- Do not restructure the codebase.
- Prioritize correctness over verbosity.

---

## Final Output

After completion, summarize:

- Files updated or created
- Key changes made
- CLI mismatches corrected
- Deprecated references removed
- Any gaps discovered
- Any architectural ambiguities that require clarification in future work
