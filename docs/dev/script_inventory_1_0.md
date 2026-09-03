# Script inventory (1.0 / Phase 0A)

Planning matrix for scripts and helpers. Support statuses: **supported** | **maintainer** | **internal** | **archived** | **disposable**.

Canonical script archive location: [`archive/scripts/`](../../archive/README.md) (not `scripts/archive/`).

## Summary

| Status | Count |
|--------|------:|
| supported | 4 |
| maintainer | 21 |
| internal | 8 |
| archived | 3 |
| disposable | 8 |

## Inventory rows

| path | purpose | intended user | current callers | documented | tested | risk | platform | deps | validity | support status | action |
|------|---------|---------------|-----------------|------------|--------|------|----------|------|----------|----------------|--------|
| `transcriptx` (`pyproject` console) | Launch Streamlit web app | end user | README, install docs, Docker ENTRYPOINT | yes | yes (indirect) | read-only | any | package | valid | supported | retain supported |
| `transcriptx.sh` | Native venv install + launch (`.transcriptx`; CUDA left available unless `TRANSCRIPTX_FORCE_CPU=1`) | end user | README, installation.md | yes | partial | mutates venv | macOS/Linux | requirements.txt | valid | supported | retain supported |
| `scripts/whispermlx-missing.py` | Batch whispermlx for MP3s missing JSON | end user | transcription.md; tests/scripts | yes | yes | writes transcripts | Apple Silicon typical | whispermlx (external) | valid | supported | retain supported |
| `scripts/inbox-watch.py` | Host inbox watch: convert audio + copy transcripts; delegates STT to whispermlx-missing | end user | transcription.md; directory_watcher.md; tests/scripts | yes | yes | writes recordings + copies transcripts | macOS typical (ffmpeg + whispermlx) | ffmpeg; whispermlx-missing | valid | supported | retain supported |
| `scripts/audio_preprocess.py` | Assess/preprocess audio before external transcription | power user | System → Tools; transcription.md; ROADMAP theme G1 | yes | yes | writes audio | any | pydub/ffmpeg | valid | maintainer | retain CLI; GUI under System → Tools |
| `scripts/audio_merge.py` | Merge split recordings into one MP3 | power user | System → Tools; transcription.md; ROADMAP theme G1 | yes | yes | writes audio | any | ffmpeg | valid | maintainer | retain CLI; GUI under System → Tools; **G1** transcript stitch still open |
| `scripts/release/assert_compose_bind.sh` | Canonical compose bind/port asserts | maintainer | CI | yes (release_governance) | CI | read-only | Docker | compose | valid | maintainer | retain internal |
| `scripts/release/stale_refs.sh` | Forbidden stale refs + TODO gate | maintainer | CI | yes | CI | read-only | any | ripgrep-like | valid | maintainer | retain internal |
| `scripts/release/clean_env_audit.sh` | Wheel + clean venv pip-check/audit | maintainer | CI / release | yes | CI | creates temp venv | any | pip-audit | valid | maintainer | retain internal |
| `scripts/release/image_pip_check.sh` | pip check inside Docker image | maintainer | CI | yes | CI | read-only | Docker | image | valid | maintainer | retain internal |
| `scripts/release/check_denylist.py` | Enforce path_denylist.toml | maintainer | secrets_check, CI | yes | CI | read-only | any | — | valid | maintainer | retain internal |
| `scripts/release/check_tracked_data.py` | Enforce tracked_data_allowlist | maintainer | CI | yes | CI | read-only | any | — | valid | maintainer | retain internal |
| `scripts/release/path_denylist.toml` | Denylist config | maintainer | check_denylist | yes | CI | n/a | n/a | n/a | valid | maintainer | retain internal |
| `scripts/release/tracked_data_allowlist.toml` | Allowlist config | maintainer | check_tracked_data | yes | CI | n/a | n/a | n/a | valid | maintainer | retain internal |
| `scripts/secrets_check.sh` | Wrapper → check_denylist | maintainer | CI, pre-release | yes | CI | read-only | any | — | valid | maintainer | retain internal |
| `scripts/docker-smoke-test.sh` | Compose service + `transcriptx --help` smoke | maintainer | Makefile, README (oversold) | partial | Makefile | read-only | Docker | compose | valid | maintainer | retain internal |
| `scripts/validate_registry.py` | Analysis module registry integrity | maintainer | developer_quickstart | yes | partial | read-only | any | package | valid | maintainer | retain internal |
| `scripts/clean_test_artifacts.py` | Remove `test__*` slugs/outputs | maintainer | Makefile | yes | partial | **destructive** | any | package | valid | maintainer | retain internal |
| `scripts/generate_pydantic_pilots.py` | Regen Pydantic config pilots | maintainer | config docs | yes | policy tests | writes generated | any | package | valid | maintainer | retain internal |
| `scripts/generate_dict_profile_models.py` | Regen dict-profile models | maintainer | config docs | yes | policy tests | writes generated | any | package | valid | maintainer | retain internal |
| `scripts/eval_speaker_voice_match.py` | Voice-match eval harness | maintainer | speaker voice contract | yes | partial | read-only default | any | package | valid | maintainer | retain internal |
| `scripts/measure_speaker_voice_match_index.py` | Stage-9 voice index benchmark | maintainer | index gate doc | yes | partial | writes JSON | any | package | valid | maintainer | retain internal |
| `scripts/export_run_performance_snapshot.py` | Prometheus textfile of run perf | maintainer | run_performance.md | yes | partial | read-only scan | any | package | valid | maintainer | retain internal |
| `scripts/backfill_speaker_profiles_from_maps.py` | Offline speaker-profile backfill | maintainer | services/contracts tests | yes | yes | **destructive** with `--apply` | any | package | valid | maintainer | retain internal |
| `tools/emotion_family_calibrate.py` | Emotion-family calibration helper | maintainer | calibration protocol | yes | partial | writes calibration artifacts | any | package | valid | maintainer | retain internal |
| `scripts/bench_pipeline_cold_warm.py` | Cold/warm pipeline import timing | developer | COMPLEXITY_GATES | yes | no | read-only | any | package | valid | internal | retain internal |
| `scripts/capture_streamlit_perf_scenarios.py` | Capture Streamlit perf JSONL | developer | perf assessment | partial | no | writes JSONL | any | streamlit | valid | internal | retain internal |
| `scripts/streamlit_perf_report.py` | Summarize Streamlit perf JSONL | developer | perf assessment | partial | no | read-only | any | — | valid | internal | retain internal |
| `scripts/log_code_size.py` | Append LOC to code_size.log | developer | none | no | no | writes log | any | — | valid | internal | retain internal |
| `scripts/install_llvm_macos.sh` | Homebrew LLVM for llvmlite | developer | install docs (macOS) | partial | no | mutates brew | Darwin | Homebrew | valid | internal | retain internal |
| `scripts/install_librosa_macos.sh` | macOS librosa+LLVM helper | developer | install docs (macOS) | partial | no | mutates env | Darwin | Homebrew | valid | internal | retain internal |
| `Makefile` targets (`test-*`, `docker-smoke`, `docs*`, `perf-envelopes`, `clean-test-artifacts`) | Dev/CI lanes wrapping scripts | maintainer | CONTRIBUTING / tests README | yes | CI | varies | any | pytest | valid | maintainer | retain internal |
| `archive/scripts/validate_dependencies.py` | Historical dependency validator | historical | none | archived banner | no | n/a | n/a | n/a | stale | archived | retain (archived) |
| `archive/scripts/validate_transcript_storage.py` | Historical storage layout check | historical | none | archived banner | no | n/a | n/a | n/a | stale | archived | retain (archived) |
| `archive/scripts/run_tests_with_timeout.py` | Historical timeout test runner | historical | none | archived banner | no | n/a | n/a | n/a | stale | archived | retain (archived) |
| `activate_env.sh` | Activate `.venv` (conflicts with `.transcriptx`) | developer | setup_env | stale | no | env mutate | any | — | **removed 0.9.1** | disposable | deleted |
| `scripts/setup_env.sh` | Interactive venv/Docker menu; dead compose refs | developer | activate_env | stale | no | env mutate | any | — | **removed 0.9.1** | disposable | deleted |
| `scripts/release/repo_hygiene_audit.py` | Phase 0A hygiene checks (allowlist, paths, banners, …) | maintainer | CI release-checks | yes | warn + strict subset | read-only | any | — | valid | maintainer | retain; `--checks` subset (**0.9.5**) |
| `scripts/release/build_docs.sh` | Sphinx HTML build wrapper | maintainer | `make docs` / CI docs | yes | CI | writes `_build` | any | `[docs]` | valid | maintainer | retain (**0.9.5**) |
| `scripts/release/assemble_pages_site.sh` | Assemble `website/` + Sphinx `/guide/` for Pages | maintainer | `make pages-site` / Pages workflow | yes | Pages | writes `_site` | any | `[docs]` | valid | maintainer | retain |
| `scripts/release/regen_module_docs.py` | Regen module catalog + quality-audit scaffold | maintainer | `make docs-gen` | yes | no | writes docs | any | package import | valid | maintainer | retain (**0.9.5**) |
| `scripts/release/perf_envelope_recipe.py` | Print perf-envelope measurement recipe | maintainer | `make perf-envelopes` | yes | release unit | read-only | any | package import | valid | maintainer | retain (**0.9.7**) |
| `scripts/generate_demo_runs.py` | Bundled demo pack installer (0.9.6 trial) | maintainer | — | n/a | n/a | n/a | n/a | n/a | **removed** (Guided/demo trial ended) | disposable | deleted |
| `archive/scripts/build_docs.sh` | Historical Sphinx builder (pre-revive) | historical | none | archived banner | no | writes `_build` | any | — | archived | archived | retain (archived); live builder is `scripts/release/build_docs.sh` |
| `scripts/docker-data-setup.sh` | Data download via wrong image / missing helpers | developer | none | stale | no | Docker mutate | Docker | missing peers | **stale** | disposable | delete |
| `scripts/docker-clean.sh` | `compose down` + unscoped system/volume prune | developer | none | no | no | **destructive** | Docker | — | stale | disposable | delete |
| `scripts/cleanup.sh` | Broad temp/cache wipe | developer | none | no | no | **destructive** | any | — | stale | disposable | delete |
| `scripts/manage_dependencies.sh` | Dep validation tied to `.transcriptx` only | developer | none | stale | no | env mutate | any | — | **stale** | disposable | delete |
| `scripts/README_test_analysis_assess.md` | Docs for missing `test_analysis_assess.py` | — | perf docs | orphan | n/a | n/a | n/a | n/a | stale | disposable | delete |
| `tests/web/gui_acceptance/scripts/*` | AppTest Streamlit entry fixtures | developer (tests) | gui acceptance | yes | yes | test-only | any | streamlit | valid | internal (test) | retain (test fixtures; not product tooling) |
| `.cursor/commands/backup.md` | Agent backup playbook with owner absolute paths | maintainer | agent | yes | n/a | n/a | local | n/a | stale paths | internal | rewrite paths to `$REPO_ROOT` |

## Early cleanup priorities (execution order)

1. ~~Delete stale setup: `scripts/setup_env.sh`, `activate_env.sh`~~ (**done 0.9.1**)
2. ~~Archive broken `scripts/build_docs.sh` → `archive/scripts/build_docs.sh`~~ (**done 0.9.1**; live builder revived as `scripts/release/build_docs.sh` in **0.9.5**)
3. Delete misleading/destructive Docker helpers: `docker-data-setup.sh`, `docker-clean.sh`, `cleanup.sh`, `manage_dependencies.sh`
4. Delete orphan `scripts/README_test_analysis_assess.md`
5. Fix `.cursor/commands/backup.md` absolute paths
6. Correct README claim that `docker-smoke-test.sh` writes an inline transcript (Phase 0B if not earlier)
7. Confirm scripts are not in Docker image package data (Docker does not `COPY scripts/`)

## Notes

- Public packaging exposes only `transcriptx` console script.
- After disposable deletes, update any docs that still reference removed helpers.
- Maintainer tooling stays under `scripts/` and `scripts/release/`; do not present as end-user product commands.
