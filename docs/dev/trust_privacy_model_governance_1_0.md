Type: PRODUCT
Authority: self

# Trust, privacy, and model governance (1.0)

**Status:** planning  
**Programme:** [pre_release_roadmap_1_0.md](pre_release_roadmap_1_0.md) §13  
**Related:** [release_severity_triage_1_0.md](release_severity_triage_1_0.md), [dependency_audit.md](dependency_audit.md)

Mandatory gate before 1.0. Missing licence/privacy truth for shipped models is a release blocker; incomplete polish of notices may be a known limitation only where legal/privacy risk is absent.

## Checklist

- [ ] Third-party model and dataset **licence inventory**
- [ ] Model download origins and **gated-model** requirements
- [ ] Voice embedding and speaker-identity **privacy wording**
- [ ] Confirmation that **no telemetry or remote processing** occurs unless explicitly configured
- [ ] Secrets and **absolute-path** audit
- [ ] Dependency **vulnerability and licence** checks
- [ ] **AI output labelling**
- [ ] Model, prompt, and analytical-semantics identity in artifacts where needed
- [ ] Explicit definition of what **“reproducible”** means for stochastic LLM output

## Known limitations + model/dependency matrix (skeleton)

| Component | Licence | Download / gated? | Privacy notes | 1.0 posture |
|-----------|---------|-------------------|---------------|-------------|
| *(fill)* | | | | |

Known limitations draft lives here until a dedicated user-facing page exists; link from ROADMAP / release notes at RC.
