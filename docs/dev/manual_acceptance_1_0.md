Type: PRODUCT
Authority: self

# Manual acceptance suite (1.0)

**Status:** planning  
**Programme:** [pre_release_roadmap_1_0.md](pre_release_roadmap_1_0.md) §15  
**Related:** [gui_acceptance_residual_checklist.md](gui_acceptance_residual_checklist.md), [release_severity_triage_1_0.md](release_severity_triage_1_0.md)

Authoritative human acceptance checklist for principal journeys. Automated GUI acceptance (`make test-gui-acceptance`) remains complementary, not a substitute.

## Environments

| Env | Notes |
|-----|-------|
| Docker Compose (recommended) | Fresh volumes where practical |
| Native (if claiming support) | After install-profile audit |

## Principal journey

- [ ] Install / launch web UI
- [ ] Import transcript into managed library
- [ ] Run analysis with a default / Guided preset
- [ ] Understand results (Overview / Insights / Charts / Artifacts)
- [ ] Recover from a deliberate failure (missing dep, bad path, or cancelled run)
- [ ] Export or download artifacts
- [ ] (When shipped) Guided vs Full controls switch
- [ ] (When shipped) Load demo project / remove demo project

## Accessibility / browsers

- [ ] Keyboard reachability of principal controls
- [ ] Supported browser smoke (document which browsers)
- [ ] Contrast / focus visibility spot-check on Home, Import, Run, Insights

## Recording

Record pass / fail / skip with severity ([release_severity_triage_1_0.md](release_severity_triage_1_0.md)) in the release-evidence notes for the intended commit.
