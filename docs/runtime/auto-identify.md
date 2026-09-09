# Auto-identify speakers

After a transcript is admitted, TranscriptX can try to replace diarized labels (`SPEAKER_00`, …) with readable names, and optionally link those speakers to existing longitudinal profiles.

This page is the operator reference. Manual naming walkthrough: [Identify and name speakers](../workflows/speaker-identification.md). Invariants: [speaker_profiles_voice_v1.md](../contracts/speaker_profiles_voice_v1.md). USB / inbox ingest: [host-stt.md](host-stt.md#host-inbox-watcher-inbox-watch).

It is probabilistic matching, not identity verification. Review badges and override names in Speaker Identification.

## Two independent knobs

| Knob | Effect when on |
|------|----------------|
| **Auto-name** | Write display names on the speaker-map sidecar so Transcript shows people instead of `SPEAKER_*` |
| **Auto-link** | Create a longitudinal profile link with `link_method: auto_identified` when a matched enrolled or uniquely named profile exists |

Both default **off**. They are orthogonal: names without links, links without names, or both.

What it does **not** do:

- Overwrite an effective human name or a live profile link
- Create a new profile from a first-meeting name heard in the dialogue
- Enrol voice samples into the ECAPA reference corpus (`auto_identified` stays `suggestion_assisted` / `ineligible_trust` until you promote)
- Force a label when voice and text disagree, or when two speakers claim the same name or profile (leaves `SPEAKER_*`)

## Where it runs

| Surface | How |
|---------|-----|
| **Settings → Speakers** | “Auto-identify on ingest” stores defaults in `{config_dir}/identify.json` (`auto_name`, `auto_link`, `style_only_apply`). The in-app G2 watcher uses this file after a successful auto-import. |
| **Speaker Identification** | **Apply auto-identify** on a managed library transcript. Badges show auto-named / auto-linked. Rename or relink as usual. |
| **Host inbox-watch** | `--auto-name` / `--auto-link` (and `--no-auto-*`). `--auto-name` implies `--admit` and turns auto-link on unless you pass `--no-auto-link`. Env: `INBOX_WATCH_AUTO_NAME` / `INBOX_WATCH_AUTO_LINK`. |
| **Admit helper** | `python -m transcriptx.admit_originals --auto-name --auto-link` after a successful admit (admit still succeeds if identify fails). |
| **Standalone CLI** | `python -m transcriptx.identify_speakers` (not a `transcriptx <subcommand>`). |

USB drop → convert → transcribe → admit → named transcript:

```bash
inbox-watch --watch --auto-name
# names only:
inbox-watch --watch --auto-name --no-auto-link
```

Standalone on files already in the library:

```bash
python -m transcriptx.identify_speakers --path FILE.json --auto-name --auto-link
python -m transcriptx.identify_speakers --all-unnamed --dry-run
```

`--dry-run` prints fusion decisions and does not write maps or links. CLI flags override `{config_dir}/identify.json` for that invocation.

Host-script merge order, env keys, and `--admit-python` live in [host-stt.md](host-stt.md#host-inbox-watcher-inbox-watch). Returning speakers need enrolled trusted voice for the voice channel; in-transcript names can still label a first meeting (auto-name only — no new profile).

## How fusion decides

Three local channels contribute candidates; an explicit table then apply or skip:

1. **Voice** — strong unique ECAPA suggestion against enrolled references (voice privacy on, corpus not empty).
2. **Mentions** — self-introductions and vocatives in the transcript text; unique-winner clustering; optional unique match to an existing profile display name.
3. **Style** — function-word / turn / question vectors versus prior linked text. Used as corroboration. Style-only apply stays off unless `style_only_apply` is enabled in `identify.json`.

Apply order (per diarized ID): strong unique voice (skip the speaker if a mention disagrees); else a unique mention; else strong style if that knob is on; else leave unnamed. A name or profile claimed by two speakers in the same transcript skips both.

Disposable review dump: `speaker_profiles/.cache/identify/{managed_id}.identify.v1.json`. Confirmed links and speaker-map sidecars remain the identity / display authorities.

Eval fixtures: `scripts/eval_speaker_identify_fusion.py`. Voice thresholds stay provisional — [known limitations](../known_limitations.md#voice-identity-privacy).

## Review

Open **Speaker Identification** after ingest. Auto-named / auto-linked badges mark machine writes. Saving a name or linking a profile from the workspace replaces the auto result the same way as a manual first pass.

Downstream speaker cards and per-speaker modules still need human-readable names. A prior analysis run may keep old `SPEAKER_*` labels until you re-run modules that key on speaker identity.

## Related

- [Identify and name speakers](../workflows/speaker-identification.md) — manual walkthrough
- [Browse speaker profiles](../workflows/speakers.md) — longitudinal directory
- [Host STT automation](host-stt.md) — inbox-watch flags
- [Directory watcher](directory_watcher.md) — in-app G2 auto-import
- [Settings](settings.md) — Speakers tab
- [STORAGE.md](STORAGE.md) — `identify.json` and `.cache/identify/`
- [Public surfaces](../public_surfaces.md) — supported helpers
- [CLI / Python API](../generated/cli.md) — `python -m transcriptx.identify_speakers`
