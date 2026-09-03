Type: GUIDE
Authority: docs/DEV_INDEX.md

# Documentation archive

Historical design, assessment, and migration records. **Not** live product or support policy.

Archived files carry an **Archived / superseded** banner and should link to a current authority.

## Layout

| Directory | Contents |
|-----------|----------|
| [assessments/](assessments/) | Stocktakes, audits, release-hygiene notes, test assessments |
| [plans/](plans/) | Completed refactor / config / sprint plans |
| [investigations/](investigations/) | Dependency conflicts, discovery notes, platform evidence |
| [migrations/](migrations/) | Completed migration / compatibility tables |

## Index

### Assessments

- [assessment-2026-03-10.md](assessments/assessment-2026-03-10.md) — superseded by stocktake
- [PHASE0_INVENTORY.md](assessments/PHASE0_INVENTORY.md)
- [scikit-learn-upgrade-assessment.md](assessments/scikit-learn-upgrade-assessment.md)
- [maintenance_release_hygiene_2026-04-01.md](assessments/maintenance_release_hygiene_2026-04-01.md)
- [shim_inventory.md](assessments/shim_inventory.md)
- [group_functionality_audit_2026-07-17.md](assessments/group_functionality_audit_2026-07-17.md)
- [streamlit_ui_test_assessment_2026-07-18.md](assessments/streamlit_ui_test_assessment_2026-07-18.md)
- [analysis_run_performance_assessment_2026-07-19.md](assessments/analysis_run_performance_assessment_2026-07-19.md)
- [run_cleanup_refactor_plan_assessment.md](assessments/run_cleanup_refactor_plan_assessment.md)
- [web_fragment_pr_audit_table.md](assessments/web_fragment_pr_audit_table.md)
- [group_charts_phase4_outcome_table.md](assessments/group_charts_phase4_outcome_table.md)
- [TEST_SUITE_ASSESSMENT.md](assessments/TEST_SUITE_ASSESSMENT.md)

### Plans

- [sprint_archive.md](plans/sprint_archive.md)
- [refactor_top3_index_2026-07-16.md](plans/refactor_top3_index_2026-07-16.md)
- [export_system_refactor_plan.md](plans/export_system_refactor_plan.md)
- [rename_corrections_orchestrator_split_plan.md](plans/rename_corrections_orchestrator_split_plan.md)
- [shared_analysis_io_refactor_plan.md](plans/shared_analysis_io_refactor_plan.md)
- [run_cleanup_refactor_contracts.md](plans/run_cleanup_refactor_contracts.md)
- [config_knobs_refactor_plan.md](plans/config_knobs_refactor_plan.md)
- [config_ownership_collapse_plan.md](plans/config_ownership_collapse_plan.md)
- [dict_profile_stores_spike.md](plans/dict_profile_stores_spike.md)
- [pydantic_migration.md](plans/pydantic_migration.md)
- [file_override_behaviour_matrix.md](plans/file_override_behaviour_matrix.md)
- [stats_summary_surface_decision_2026-04-21.md](plans/stats_summary_surface_decision_2026-04-21.md)

### Investigations

- [convokit_dependency_conflict.md](investigations/convokit_dependency_conflict.md)
- [bertopic_platform_evidence.md](investigations/bertopic_platform_evidence.md)
- [group_charts_prosody_temporal_discovery.md](investigations/group_charts_prosody_temporal_discovery.md)

### Migrations

- [chart_evidence_migration.md](migrations/chart_evidence_migration.md)
- [rename_corrections_compat_table.md](migrations/rename_corrections_compat_table.md)
- [whisperx_transcriptionconfig.md](migrations/whisperx_transcriptionconfig.md)

## Policy

- Gitignore is **not** an archive mechanism; this tree is tracked.
- Do not present archived plans as active roadmaps.
- Executable historical scripts live under [`archive/scripts/`](../../archive/README.md), not here.
