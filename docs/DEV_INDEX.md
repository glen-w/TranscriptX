Type: GUIDE
Authority: docs/dev/CONTRIBUTING.md

# Developer documentation index

Active developer and maintainer docs. Historical material is listed only via [ARCHIVE_INDEX](archive/ARCHIVE_INDEX.md).

## Phase 0A / 0B programme

| Doc | Purpose |
|-----|---------|
| [documentation_inventory_1_0.md](dev/documentation_inventory_1_0.md) | Docs classification matrix |
| [script_inventory_1_0.md](dev/script_inventory_1_0.md) | Script support-status matrix |
| [pre_release_roadmap_1_0.md](dev/pre_release_roadmap_1_0.md) | 0.9.x → 1.0 programme plan |
| [local_scratch.md](dev/local_scratch.md) | `.local/` ignored scratch convention |
| [workflow_media_capture.md](dev/workflow_media_capture.md) | Regenerating workflow walkthrough screenshots/GIFs |
| [schema_epoch_inventory.md](dev/schema_epoch_inventory.md) | Schema epoch inventory + transition UX (sign-off before wipe) |
| [release_severity_triage_1_0.md](dev/release_severity_triage_1_0.md) | 1.0 hardening severity rules |
| [install_profiles_matrix.md](dev/install_profiles_matrix.md) | Install-profile planning matrix |
| [docs_architecture_1_0.md](dev/docs_architecture_1_0.md) | Docs surface architecture |
| [manual_acceptance_1_0.md](dev/manual_acceptance_1_0.md) | Manual acceptance suite skeleton |
| [analysis_quality_audit.md](dev/analysis_quality_audit.md) | Analysis quality audit template |
| [analysis_quality_audit_scaffold.md](dev/analysis_quality_audit_scaffold.md) | Generated registry rows (`make docs-gen`) |
| [analysis_quality_audit_judgements.md](dev/analysis_quality_audit_judgements.md) | Provisional Recommendation / Severity overlay |
| [performance_envelopes_1_0.md](dev/performance_envelopes_1_0.md) | Performance envelope planning |
| [trust_privacy_model_governance_1_0.md](dev/trust_privacy_model_governance_1_0.md) | Trust / privacy / model gate |
| [release_ops_support_1_0.md](dev/release_ops_support_1_0.md) | Release ops / support policy |
| [rtd_go_live_checklist.md](dev/rtd_go_live_checklist.md) | Read the Docs go-live flip steps |
| [unfamiliar_user_validation_1_0.md](dev/unfamiliar_user_validation_1_0.md) | Unfamiliar-user validation protocol |
| [overview_presentation_0_9_9.md](dev/overview_presentation_0_9_9.md) | 0.9.9 Overview/results presentation polish (post-maintainer, pre-unfamiliar-user) |

## Orientation

| Doc | Purpose |
|-----|---------|
| [developer_quickstart.md](developer_quickstart.md) | Mental model and extension points |
| [CONTRIBUTING.md](dev/CONTRIBUTING.md) | Docs authority model and sync checklist |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System shape (non-authoritative for rules) |
| [ADR-IMPORT-ORCHESTRATION.md](ADR-IMPORT-ORCHESTRATION.md) | Import orchestration ADR |
| [PRODUCT.md](PRODUCT.md) | Product definition |
| [ROADMAP.md](ROADMAP.md) | Product roadmap (0.9.x → 1.0 → 2.0) |
| [theme_a_insights_quality.md](dev/theme_a_insights_quality.md) | Theme A insights quality (deterministic/hybrid, less noise) |
| [theme_c_workspaces_ccv2.md](dev/theme_c_workspaces_ccv2.md) | Theme C CCv2 workspaces design (Speaker ID / Corrections) |
| [theme_c_invest_narrow_defer.md](dev/theme_c_invest_narrow_defer.md) | Theme C invest/narrow/defer decision |
| [release_governance.md](dev/release_governance.md) | Release evidence checklist |
| [stocktake_2026-07-17.md](dev/stocktake_2026-07-17.md) | Living decision foundation (0.9→1.0) |
| [analysis_module_backlog_2026-07-17.md](dev/analysis_module_backlog_2026-07-17.md) | Module backlog (0.9.x freeze) |

## Active engineering

| Doc | Purpose |
|-----|---------|
| [config_architecture.md](dev/config_architecture.md) | Config / settings dual-stack architecture |
| [settings_knobs_assessment.md](dev/settings_knobs_assessment.md) | Settings/knobs assessment and hardening backlog |
| [pipeline_contracts.md](dev/pipeline_contracts.md) | Pipeline layering contracts |
| [output_conventions.md](dev/output_conventions.md) | Output conventions guide |
| [export.md](runtime/export.md) | Overview ZIP / HTML / EPUB export guide |
| [run_outcome_model.md](dev/run_outcome_model.md) | Run outcome developer notes |
| [run_performance.md](dev/run_performance.md) | Analysis-run performance telemetry |
| [COMPLEXITY_GATES.md](dev/COMPLEXITY_GATES.md) | Complexity / performance gates |
| [composition_platform.md](dev/composition_platform.md) | Composition platform |
| [web_blocks.md](dev/web_blocks.md) | Web block architecture |
| [dependency_audit.md](dev/dependency_audit.md) | Dependency / CVE waiver policy |
| [bertopic_optional_module.md](dev/bertopic_optional_module.md) | BERTopic optional module |
| [emotion_family_contracts_2026-07-18.md](dev/emotion_family_contracts_2026-07-18.md) | Emotion-family contracts |
| [emotion_family_calibration_protocol_2026-07-18.md](dev/emotion_family_calibration_protocol_2026-07-18.md) | Calibration protocol |
| [speaker_voice_match_index_gate.md](dev/speaker_voice_match_index_gate.md) | Voice match index gate |
| [speaker_profiles_reference_env_index_gate.md](dev/speaker_profiles_reference_env_index_gate.md) | Reference-env index gate |
| [wave2_lexicon_linguistics_2026-07-23.md](dev/wave2_lexicon_linguistics_2026-07-23.md) | Wave 2 lexicon notes |
| [wave_b13_interaction_graphs_2026-07-23.md](dev/wave_b13_interaction_graphs_2026-07-23.md) | Wave B13 interaction graphs |
| [wave_b16_keyphrases_2026-07-24.md](dev/wave_b16_keyphrases_2026-07-24.md) | Wave B16 keyphrases |
| [gui_acceptance_residual_checklist.md](dev/gui_acceptance_residual_checklist.md) | GUI acceptance residual checklist |
| [install_verification_matrix.md](runtime/install_verification_matrix.md) | Install verification matrix |
| [docker-efficiency-baseline.md](runtime/docker-efficiency-baseline.md) | Docker efficiency baseline |

## Tests

| Doc | Purpose |
|-----|---------|
| [tests/README.md](../tests/README.md) | How to run tests |
| [tests/contracts/README.md](../tests/contracts/README.md) | Contract tests |
| [tests/quarantine/README.md](../tests/quarantine/README.md) | Quarantined tests |

## Script archive (executable)

Non-production scripts: [archive/README.md](../archive/README.md).

## Documentation archive

[archive/ARCHIVE_INDEX.md](archive/ARCHIVE_INDEX.md)
