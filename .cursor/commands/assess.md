# Maturity Assessment (# assess)

Freeze-planning stocktake for `TranscriptX`. Execute from the workspace root.

This is a **maintainer survey**, not a tag gate and not a substitute for `# pre-release` or `# refactor`. Those stay as focused commands. This file inlines their checklists so a freeze sitting does not depend on chaining files.

## Project card (fill before first use)

| Key | Value |
| --- | --- |
| Package | `transcriptx` / `src/transcriptx` |
| Default test command | `make test-fast` |
| Small fixture | `tests/fixtures/mini_transcript.json` |
| Authoritative next-tag doc | `docs/dev/release_governance.md` |
| Contract files | `docs/CONTRACT_INDEX.md` |
| Roadmap | `docs/ROADMAP.md` |
| Architecture rules | `pipeline boundaries hold; analysis stays in core; web must not own run_analysis; do not import transcribe; transcription is BYO / host-orchestrated` |
| Maturity bars (freeze / 1.0) | `public 1.0 is the GitHub Release on main; GitHub Latest matches main; transcription stays BYO; no Transcribe coupling` |
| Public landing | `https://glenwright.earth/TranscriptX/` |
| Survey directory | `docs/assessments` |

---

## Authority (hard rules)

This command **must not**:

- Change the package version or edit `CHANGELOG.md`
- Create, inspect, or approve git tags
- Push commits, or recommend a push or tag
- Implement refactors, rewrite docs via `# docs`, or run `# cleanup`
- Present itself as release governance. Authoritative next-tag checklist: `docs/dev/release_governance.md` (or `none`)

**Outcomes for mechanical checks:** `pass` / `warning` / `failure` / `skipped` (with reason). Never a silent pass.

The only intended tree write is `docs/assessments/YYYY-MM-DD-assess.md` (plus a short folder README if that file is missing). Do not write under root `assessments/` (that is `# watch`). Do not invent a CONTRACT tree. Skip a surface that does not exist (no Docker, no UI, no ROADMAP, no `gh`) and say why.

Do not assume PyPI upload unless the project actually publishes there.

---

## 0. Run backup first (mandatory)

This command writes a tracked survey file. Run `# backup`. Wait for it. Skip only if `# deep-test` already backed up in this session (note that in the survey). Backup failure is a **warning**; continue the report.

---

## 1. Identity and git facts

- One sentence: what the README (or first contract file) says this product is.
- Git: branch, dirty tree (`git status --short --untracked-files=all`), ahead/behind default branch, latest tag, `pyproject.toml` version.
- GitHub Latest Release when `gh` works. Missing `gh` / no GitHub remote → `skipped`.
- Flag splits among tag, default branch, package version, GitHub Latest, and `https://glenwright.earth/TranscriptX/`.

Dirty or unexpected paths → **failure** for local readiness (do not advise tagging). No git repo → **warning**. Behind remote → **warning**.

---

## 2. SLOC

Measure **source lines of code** (blanks and comments stripped). Markdown, JSON, YAML, and TOML are not code.

Prefer `python3 scripts/count_sloc.py --root .` when that script is in the repo. Otherwise `python3 "$HOME/.cursor/skills/count-sloc/scripts/count_sloc.py" --root .`. `--install` only in a local session when tokei / scc / cloc / radon are missing. Cloud or remote sandbox: do not `--install`.

Missing tools → **skipped**. Do not invent counts.

Quote the three headlines:

- **Substantive product SLOC** — median of tokei/scc/cloc for application source, excluding tests and generated build. Min-max range.
- **Maintained SLOC** — product + tests + scripts/tools.
- **Python-only product SLOC** — trio median vs radon. If radon differs by more than ~10%, do not average it in; say so.

---

## 3. Pre-release checks (inlined)

Same elements as `# pre-release`. Prefer `scripts/release/` or `scripts/` when present; missing script → `skipped (script not present)`, then run the inline equivalent.

Typical names (use what exists; do not invent): compose bind (`make docker-smoke` / `assert_compose_bind.sh`), secrets (`secrets_check.sh`), tracked data (`check_tracked_data.py`), stale refs (`stale_refs.sh`).

### 3.1 Worktree

Covered in §1. Repeat the outcome here.

### 3.2 Tests

- Interpreter gate: `python --version` must satisfy `requires-python` in `pyproject.toml`.
- Run `make test-fast` (and smoke/contract Makefile targets when present).
- Failures → **failure**. Unavailable pytest/env → **skipped**.
- Default suite stays fast and offline. Do not require live models or network.

### 3.3 Packaging

- `python -m build` when packaging is set up (install `build` if needed).
- Install wheel into a throwaway venv when practical; confirm `import transcriptx` and version.
- Inspect sdist/wheel: user data, `.venv`, caches, and secrets must not ship. Unexpectedly large artifacts → **failure**.
- Missing packaging config → **skipped**.

### 3.4 Compose + Docker (optional)

- Only if `Dockerfile`, `docker-compose.yml`, or `compose.yaml` exists.
- Run bind/smoke scripts when present (source-level checks do not need a daemon).
- When Docker is available: a documented image smoke if one exists.
- Unavailable or no packaging → **skipped**. Never pretend pass.
- Do not run `docker compose down` or prune.

### 3.5 Hygiene

- Run secrets / tracked-data / stale-ref scripts when present.
- Spot-check that data dirs, large binaries, and `.env` are not tracked.
- Denylist / secrets / tracked-data failure → **failure**. Do not recommend tagging or pushing.

### 3.6 Docs + backup/restore (read-only)

Compare this branch / dirty worktree against the base branch for new or changed features, output artifacts, and settings. **Flag drift; do not fix it.**

| Check | Pass when | Failure / warning |
| --- | --- | --- |
| Documented | Each new surface appears in the right doc layer | Undocumented user-visible knob → **failure**; minor index drift → **warning** |
| `# backup` paths | Code/config/docs included; generated/runtime dirs excluded | New top-level code/doc path missing from backup includes → **failure** |
| Restore / reopen | Persisted settings still load; commands restorable from `"$BACKUP_ROOT/custom-commands/"` | Broken reopen → **failure** |

No new surfaces → **pass** (N/A).

### 3.7 Soft / optional

- `black --check` / `ruff check` / `mypy` → report; do not auto-fix.
- CI status via `gh` when available → informational; missing → **skipped**.
- Output sanity on `tests/fixtures/mini_transcript.json` when there is a cheap golden-path command. Missing fixture → **skipped**.

---

## 4. Refactor assessment (inlined)

Do not change code. Same headings as `# refactor`. Flag violations of `pipeline boundaries hold; analysis stays in core; web must not own run_analysis; do not import transcribe; transcription is BYO / host-orchestrated`.

1. **Complexity** — long functions or files, deep nesting, heavy branching, high cognitive load.
2. **Duplication** — repeated logic, similar helpers, copy-paste.
3. **Structure** — mixed responsibilities, tight coupling, unclear data flow, architecture-rule breaks.
4. **Naming** — ambiguous, inconsistent, misleading, overly generic utilities.
5. **Test coverage gaps** — core logic thin; fragile areas that should refactor before extension.
6. **Risk** — large/central/hot files; regression magnets; modules that would block future features.

Close with **top 5 candidates**, why they matter, suggested order, and risk (low / medium / high). Incremental only. No full rewrites unless strictly necessary.

---

## 5. Security / threat model

Whole-repo posture, not a branch-diff review. Do not require `# review-security`. If a dirty diff exists, you may note it; do not treat that as this section.

Cover, and skip with reason when the surface is absent:

- Secrets and gitignore: `.env`, credentials, dumps, user data not tracked or zipped
- Default-offline / network: default entrypoint must not call the network unless the product says it does
- Loopback UI if a UI exists; sibling ports are not this product's
- Store-of-record boundaries (mail root, library, notebooks stay owned elsewhere when that is the contract)
- Dependency / pin / license glance (`pyproject.toml`, lockfile if any)
- Web injection / CSP if a HTML UI exists

Failures are hygiene or contract breaks. Hypothetical hardening is a recommendation, not a `failure`.

---

## 6. Roadmap honesty

Read `docs/ROADMAP.md` (skip if `none` or missing) against the code and `docs/CONTRACT_INDEX.md`. If `docs/COMPARISON.md` exists, score whether it still matches the pitch.

Classify items as **shipped / thin / parked / non-goals**. Flag:

- Docs that claim shipped behavior the tree does not have
- Code that outruns the freeze bar in `public 1.0 is the GitHub Release on main; GitHub Latest matches main; transcription stays BYO; no Transcribe coupling`
- Parked or non-goal work that has started to land anyway

Do not invent a roadmap file.

---

## 7. Maturity scorecard

Score 1–10. Higher is closer to the freeze line in `public 1.0 is the GitHub Release on main; GitHub Latest matches main; transcription stays BYO; no Transcribe coupling`, not more commits.

| Area | Score | Why |
| --- | --- | --- |
| Process |  | tests, CI, types, goldens, doctor |
| Product |  | vs `public 1.0 is the GitHub Release on main; GitHub Latest matches main; transcription stays BYO; no Transcribe coupling` |
| Public / landing |  | `https://glenwright.earth/TranscriptX/`, Ko-fi, GitHub Latest vs tag vs `pyproject` |
| Packaging |  | wheel/sdist, extras, Docker if any |
| Docs |  | README honesty; contract tree only if the project already has one |
| Ops / first-run |  | `init` / `doctor` / compose when they exist |

Operator golden path: can a stranger follow the README to a first successful run on the small fixture without a maintainer at their elbow? Say yes, almost, or no, with the missing step.

---

## 8. Freeze implications

- **Lock** — what should stop moving for this freeze
- **May still thicken** — allowed depth without a new surface
- **Needs a contract revision** — work that must not sneak in under the freeze

End with a **freeze-planning** line: `CONFIDENT` / `NEEDS FIXES` / `HIGH RISK`. Explicitly **not** a release approval.

---

## 9. Write the survey

Write `docs/assessments/YYYY-MM-DD-assess.md` (create the directory if needed). Include identity, SLOC headlines, pre-release outcome table, top 5 refactors, security findings, roadmap flags, scorecard, freeze implications, and the confidence line.

If `docs/assessments/README.md` is missing, add one paragraph: these files are maintainer surveys, not contracts; ROADMAP / CONTRACT still win. If a README already exists, leave it.

Chat gets the scorecard, the confidence line, and the survey path.

### Pre-release outcome table (copy into the survey)

| Area | Outcome |
| --- | --- |
| Worktree | pass / failure / warning |
| Tests | pass / failure / skipped |
| Packaging | pass / failure / skipped |
| Docker | pass / failure / skipped |
| Hygiene | pass / failure / skipped |
| Docs + backup/restore | pass / failure / warning / skipped |
