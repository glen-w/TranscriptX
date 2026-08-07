# Medium corpus Balanced recipe — measured 2026-08-07

- Environment: Docker Compose (`transcriptx-web`)
- Preset: `analysis_preset=balanced`
- Corpus: 6 transcripts (Medium class ~5–10)
- Batch start: 13:04:45 → end: 13:14:05 (~9.3 min wall)
- Sum of per-run `wall_clock_duration_ms`: ~560 s
- Outcome: all `final_status=succeeded`, 0 module failures

| Transcript | Run id | wall_s | modules_run / skipped / failed |
|---|---|---:|---|
| 250703_mariela_workshop_briefing | 20260807_130445_07885487 | 2.9 | 5 / 25 / 0 |
| 250703_fact_sheets_comms | 20260807_130448_07888475 | 6.8 | 5 / 25 / 0 |
| 251113_CSE_Thomas_Jonas | 20260807_130455_07895311 | 143.0 | 30 / 0 / 0 |
| 251230_pub_rant_people_get_angry_at_the_wrong_thing | 20260807_130718_08038385 | 43.2 | 25 / 5 / 0 |
| 260608_Neptune_Forum_6 | 20260807_130801_08081665 | 90.1 | 30 / 0 / 0 |
| 260701_ESEE_conference_3_Ana_presentation | 20260807_130931_08171924 | 273.8 | 30 / 0 / 0 |

Outputs under `HOST_OUTPUT_DIR` (`Documents/transcriptx outputs/…`).
Recorded in `docs/dev/manual_acceptance_1_0.md` §3.12.
