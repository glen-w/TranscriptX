# Unfamiliar-user validation (1.0) — run kit

**Status:** executable kit prepared in **0.9.8**; cohort who/when remains owner judgement ([pre_release_roadmap_1_0.md](pre_release_roadmap_1_0.md) §20)  
**Programme:** [pre_release_roadmap_1_0.md](pre_release_roadmap_1_0.md) §14  
**Related:** [manual_acceptance_1_0.md](manual_acceptance_1_0.md), [release_severity_triage_1_0.md](release_severity_triage_1_0.md), [known_limitations.md](../known_limitations.md)

The 1.0 success criterion centres on an unfamiliar user. Run during indicative **0.9.x hardening / pre-RC** once install and principal journeys are stable enough to evaluate. **Do not execute this round as part of the 0.9.8 code cut** — this file prepares the kit so the round can run without inventing protocol.

Prepared evidence ≠ measured evidence ≠ signed-off evidence.

---

## 1. Mandatory protocol (summary)

- [ ] Two to five people who have **not** developed TranscriptX
- [ ] At least one relatively **non-technical** user
- [ ] **Fresh machine** or fresh environment
- [ ] **No live coaching** unless they become completely blocked (see §6)
- [ ] Record: installation time; time to first useful result; blockers; misunderstood terminology; abandoned journeys

---

## 2. Cohort slots (owner fills who/when)

| Slot | Role | Eligibility | Who (owner) | When | Consent on file |
|------|------|-------------|-------------|------|-----------------|
| 1 | Non-technical | No TranscriptX development; limited CLI comfort OK | | | [ ] |
| 2 | Thoughtful generalist | Has used similar tools; not a maintainer | | | [ ] |
| 3 | Optional | Researcher / analyst emerging audience | | | [ ] |
| 4 | Optional | | | | [ ] |
| 5 | Optional | | | | [ ] |

**Eligibility criteria**

- Has not authored TranscriptX code or release docs
- Can use a browser; may or may not know Docker/Python
- Agrees to privacy-safe participation (§5)
- Uses only synthetic / demo / consented sample transcripts — **no private personal recordings** unless the participant owns them and consents in writing

**Environment requirements**

- Fresh machine **or** fresh disposable data root + clean install path from [install_verification_matrix.md](../runtime/install_verification_matrix.md)
- Prefer Docker Compose for predictability; native only if claiming native support
- Record OS, architecture, install profile, package version, SHA

**Curated sample stack (optional facilitator prep)**

For a disposable UI that only mounts the facilitator sample set (not the maintainer library), use the sibling tree `../transcriptx_test/` and:

```bash
# Once per fresh data tree (or after wiping data/): write the epoch-1 marker
python -c "from pathlib import Path; from transcriptx.core.utils.schema_epoch import write_epoch; write_epoch(Path('../transcriptx_test/data'))"
docker compose -f docker-compose.unfamiliar-user.yml up -d transcriptx-web
# Register pre-copied managed transcripts (Home uses the slug index, not raw disk scan)
docker compose -f docker-compose.unfamiliar-user.yml exec -T transcriptx-web python - <<'PY'
from transcriptx.core.utils.file_discovery import discover_managed_transcript_paths
from transcriptx.io.admit_and_register import _try_register
for p in discover_managed_transcript_paths():
    print(_try_register(p), p.name)
PY
```

Then open http://127.0.0.1:8502 (port **8502** so it does not collide with the main stack on 8501). This compose file is standalone (does not merge `docker-compose.override.yml`). Defaults point at `transcriptx_test_transcripts` / `transcriptx_test_recordings` / `transcriptx_test_outputs` plus disposable `data/`, `config/`, and `transcript-inbox/` under that tree. The data root needs `schema_epoch.json` (epoch **1**) once Streamlit has written any content under it — otherwise the schema-epoch gate blocks analysis. Files copied into the transcripts mount still need **registration** into `.transcriptx_index.json` (under outputs) for Home to list them; Library pickers can also see on-disk JSON. See [docker.md](../runtime/docker.md).

---

## 3. Facilitator script (principal journey)

Goal path: **install → first useful result → export**. Timing starts at first install instruction.

1. Hand participant the README / website landing (or printed quickstart). Do **not** narrate steps.
2. Ask them to install and open the UI.
3. Ask them to import a provided sample transcript (facilitator-supplied file; no in-app demo pack).
4. Ask them to run an analysis and find something useful in Overview / Insights / Charts.
5. Ask them to export or download results.
6. Optional: explore Settings / advanced pages — only if time remains and no distress.

**Permitted facilitator prompts** (examples)

- “What are you trying to do right now?”
- “Where are you looking for that?”
- “You can stop whenever you want.”
- Restate the high-level goal once if forgotten (“install, then get a useful result”).

**Forbidden coaching**

- Pointing at specific buttons/menus
- Dictating install commands beyond what public docs already show on their screen
- Explaining product jargon unprompted
- Fixing errors for them (except emergency intervention §6)

**Log every intervention** (coaching invalidates blockage and time-to-first-result evidence for that segment).

---

## 4. Timing sheet

| Participant | Install start | UI up | First import | First useful result | Export done | Abandoned? | Notes |
|-------------|---------------|-------|--------------|---------------------|-------------|------------|-------|
| | | | | | | | |

Definitions:

- **Install time:** start of install instructions → UI reachable
- **Time to first useful result:** UI up → participant affirms a useful insight/chart/summary (their words)

---

## 5. Privacy-safe participation

- **Informed consent:** purpose, voluntary nature, what is recorded, retention, withdrawal
- **Minimal recording:** prefer written observation notes; screen/audio only with explicit consent
- **Anonymisation:** participant codes (P1…); no real names in shared evidence
- **Avoid private transcript content:** use demo/synthetic samples; if personal data appears, stop (§7)
- **Secure retention:** raw notes in `.local/` scratch; accepted evidence under release-evidence tied to SHA
- **Withdrawal / deletion:** honour requests; delete identifiable raw recordings promptly

Consent checklist (per participant):

- [ ] Purpose explained
- [ ] Recording scope agreed
- [ ] Withdrawal explained
- [ ] Sample data provenance explained

---

## 6. Emergency intervention rules

Intervene immediately (and **log**) if:

- Participant is distressed
- Privacy concern / personal data exposure risk
- Unsafe deletion risk (about to wipe non-disposable data)
- Unrecoverable installation failure after reasonable self-attempts
- Exposure of personal data in UI/logs

After emergency intervention, mark timing metrics for that segment as **invalidated by coaching/intervention**.

---

## 7. Stop conditions

Stop the session (or that journey) when any of:

- Distress
- Privacy concern
- Unsafe deletion risk
- Unrecoverable installation failure
- Exposure of personal data

Record stop reason and severity.

---

## 8. Observation form (per finding)

| Field | Value |
|-------|-------|
| participant code | |
| journey step | install / import / analyse / understand / export / other |
| observation | |
| quote (optional, anonymised) | |
| blockage? | yes / no |
| terminology confusion | |
| intervention logged? | yes / no / n/a |

---

## 9. Severity worksheet → RC gate

Map **each** issue to [release_severity_triage_1_0.md](release_severity_triage_1_0.md):

| Finding ID | Summary | Severity | Blocks RC? |
|------------|---------|----------|------------|
| U-001 | | release blocker / must fix / known limitation / post-1.0 | yes if blocker or must-fix |

**Rule:** any **release blocker** or **must-fix** from this round **explicitly prevents RC entry** until fixed or reclassified with owner sign-off.

---

## 10. Post-session triage procedure

1. Consolidate observation forms + timing sheet within 24h.
2. Deduplicate findings; assign severities.
3. Copy accepted evidence to release-evidence location for the tested SHA (not only `.local/`).
4. Open or update issues for blocker / must-fix items.
5. Update programme checklist: unfamiliar-user validation evidence reviewed.
6. Known limitations / post-1.0 items → document; do not silently drop.

---

## 11. Triage reminder

Map findings to [release_severity_triage_1_0.md](release_severity_triage_1_0.md). Blockers and must-fix items from this round gate RC.
