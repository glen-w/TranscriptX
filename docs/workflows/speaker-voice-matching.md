# Assist naming across transcripts with voice

After a seed cast is named and linked, enrol trusted voice and pre-load suggestions so Speaker Identification can **propose** the same people on later managed transcripts. You still confirm each suggestion.

## Outcome

You will have enabled local voice matching, enrolled reference samples from confirmed profile links, pre-loaded suggestion caches, and seen a suggested profile on a later transcript that you can confirm.

## Starting point

- The `speaker_match` extra is installed ([Models](../runtime/models.md#longitudinal-voice-matching-speaker_match)). Default installs do not include it.
- Managed library transcripts with linked audio (enrol and analyse need speech; short turns under about eight seconds may not match).
- At least one transcript where you [named speakers](speaker-identification.md) and **created or attached** longitudinal profiles (not name-only).
- Local AI / Ollama is not required.

## What you’ll do

1. Enable voice matching and read the privacy notice.
2. Enrol trusted voice for all profiles (reference corpus).
3. Pre-load voice suggestions (sample all managed speakers).
4. Open Speaker Identification on another transcript and confirm the suggested person.

## Walkthrough

1. Open **Settings → Speakers**. Read the voice privacy notice and **enable** voice matching. Consent is stored in `privacy.voice_settings.json`. Opt-in **does not** enrol any samples.

2. Confirm you already have **active profiles with confirmed links** (from Speaker Identification → Create new profile, or Attach to an existing person). Profiles without links cannot enrol.

3. Under **Library voice batch**, choose **Refresh enrol inventory**, then **Enrol trusted voice for all profiles**. This walks confirmed links up to **Max confirmed links per voice enrol** (default 40). Archived and merged profiles are skipped.

4. When enrol finishes, choose **Refresh suggestion inventory**, then **Pre-load voice suggestions**. This analyses every non-ignored, non-collision speaker on managed transcripts into `.cache/voice`. That is the library-wide “sample all” step. An empty reference corpus still analyses but usually returns **No reliable match** — enrol first.

5. Open **Speaker Identification** on a later managed transcript. For each diarized speaker, the **Link to speaker profile** control should list a voice or name match when one is available. Review the chip, then save to confirm. Scores never write a name by themselves.

6. Optionally use **Analyse all speakers** on one transcript instead of library Pre-load when you only need that file, or after caches go stale.

## What to notice

- Enrol all builds **references**; Pre-load / Analyse all builds **queries**. Order matters.
- Ignored speakers and collision keys are skipped by Pre-load.
- Suggestion-assisted samples are not trusted references until they are enrolled after you confirm more links. Re-run Enrol all if matches stay weak.
- Duplicate profiles (two “Maya”s) make matching worse — attach to the existing person instead of creating another.
- Revoke consent or Delete voice evidence wipes samples; the enrol-cap setting survives revoke.

## You should now have…

A reference corpus for linked people, warmed suggestion caches, and a later transcript where Speaker Identification proposes a person you can confirm.

## Next

- [Identify and name speakers](speaker-identification.md)
- [Browse speaker profiles](speakers.md)
- [Settings & knobs](../runtime/settings.md#speakers)
