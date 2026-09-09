#!/usr/bin/env python3
"""Fusion-table fixtures for speaker auto-identify (no audio / SpeechBrain).

Run: python scripts/eval_speaker_identify_fusion.py
"""

from __future__ import annotations

from transcriptx.core.speaker_profiles.identify.fusion import fuse_speaker_candidates
from transcriptx.core.speaker_profiles.identify.models import ChannelCandidate


def _v(name: str, pid: str, conf: str = "strong") -> ChannelCandidate:
    return ChannelCandidate(
        channel="voice", display_name=name, profile_id=pid, confidence=conf
    )


def _m(name: str, pid: str | None = None) -> ChannelCandidate:
    return ChannelCandidate(
        channel="mention", display_name=name, profile_id=pid, confidence="possible"
    )


def main() -> int:
    cases = [
        (
            "voice_only",
            ["SPEAKER_00"],
            {"SPEAKER_00": _v("Maya", "p")},
            {},
            {},
            False,
            "apply",
        ),
        (
            "conflict",
            ["SPEAKER_00"],
            {"SPEAKER_00": _v("Maya", "p")},
            {"SPEAKER_00": _m("Jordan")},
            {},
            False,
            "skip",
        ),
        (
            "mention_only",
            ["SPEAKER_00"],
            {},
            {"SPEAKER_00": _m("Sam")},
            {},
            False,
            "apply",
        ),
        (
            "collision",
            ["SPEAKER_00", "SPEAKER_01"],
            {
                "SPEAKER_00": _v("Maya", "p"),
                "SPEAKER_01": _v("Maya", "p"),
            },
            {},
            {},
            False,
            "skip",
        ),
    ]
    failed = 0
    for name, ids, voice, mentions, style, style_only, expect in cases:
        decisions = fuse_speaker_candidates(
            speaker_ids=ids,
            voice=voice,
            mentions=mentions,
            style=style,
            style_only_apply=style_only,
        )
        actions = {d.action for d in decisions}
        ok = actions == {expect}
        print(f"{'ok' if ok else 'FAIL'} {name}: {actions}")
        if not ok:
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
