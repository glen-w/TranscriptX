Type: PRODUCT
Authority: self

# Release severity triage (1.0)

**Status:** planning / published rules  
**Programme:** [pre_release_roadmap_1_0.md](pre_release_roadmap_1_0.md) §7  
**Linked from:** [ROADMAP.md](../ROADMAP.md), [release_governance.md](release_governance.md)

Without explicit severity, hardening expands indefinitely because every imperfection looks equally important. Apply these rules during 0.9.x hardening and RC triage.

| Severity | Definition | 1.0 action |
|----------|------------|------------|
| **Release blocker** | Data loss; unsafe deletion; corrupt outputs; broken supported install; incorrect run truth; security/privacy failure | Must fix before RC/1.0; no known-limitation escape |
| **Must fix** | Principal journey broken; misleading prominent analysis; unusable error state; documentation cannot complete a supported workflow | Must fix before 1.0 |
| **May ship as known limitation** | Optional module failure; unsupported language/model/platform combination; specialist UI friction; non-critical performance problem | Document honestly; do not block 1.0 |
| **Post-1.0** | Aesthetic refactors; experimental analyses; specialist convenience; non-supported configurations | Explicitly out of scope for the release gate |

## Gate rules

- [x] Severity rules written and linked from ROADMAP / release governance
- [x] Hardening backlog tagged with severity before RC (provisional — [analysis_quality_audit_judgements.md](analysis_quality_audit_judgements.md) **0.9.7**; owner confirm)
- [ ] RC entry requires zero open release blockers and zero open must-fix items

Tag each hardening finding with one severity before scheduling work. Known limitations must be listed in release notes or a known-limitations section when shipping under that class.
