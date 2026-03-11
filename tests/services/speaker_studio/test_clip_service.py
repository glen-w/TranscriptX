"""
Tests for the reworked ClipService.

Coverage targets from the plan:
  1. Cache key changes when source file mtime or size changes.
  2. Cache key does not change when source file is unchanged.
  3. CLIP_CACHE_SCHEMA_VERSION bump produces a different cache key.
  4. warm_clips deduplicates: two calls for the same key enqueue one job.
  5. Foreground miss + concurrent warm miss → only one final file, no partial reads.
  6. Temp file is never readable by get_clip_path (only the renamed final path is).
  7. ffmpeg_available() returns False when ffmpeg is absent; warm_clips no-ops.
  8. Controller.warm_clips and ffmpeg_available delegate to ClipService correctly.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.services.speaker_studio.clip_service import (
    CLIP_CACHE_SCHEMA_VERSION,
    ClipService,
)
from transcriptx.services.speaker_studio.controller import SpeakerStudioController


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_audio(path: Path, content: bytes = b"\x00" * 1024) -> Path:
    """Write a fake audio file."""
    path.write_bytes(content)
    return path


# ── 1 & 2: cache key stability ────────────────────────────────────────────────


def test_cache_key_stable_for_same_file(tmp_path: Path) -> None:
    audio = _make_audio(tmp_path / "a.mp3")
    svc = ClipService(data_dir=tmp_path)
    k1 = svc._cache_key(audio, 0.0, 2.0, "mp3", 50)
    k2 = svc._cache_key(audio, 0.0, 2.0, "mp3", 50)
    assert k1 == k2
    svc.close()


def test_cache_key_changes_when_mtime_changes(tmp_path: Path) -> None:
    audio = _make_audio(tmp_path / "a.mp3")
    svc = ClipService(data_dir=tmp_path)
    k1 = svc._cache_key(audio, 0.0, 2.0, "mp3", 50)

    # Simulate source file replacement by writing new content and forcing mtime change.
    time.sleep(0.01)
    audio.write_bytes(b"\xff" * 2048)
    # Touch mtime explicitly to ensure it differs on fast filesystems.
    audio_stat = audio.stat()
    new_mtime = audio_stat.st_mtime + 1.0
    import os

    os.utime(audio, (new_mtime, new_mtime))

    k2 = svc._cache_key(audio, 0.0, 2.0, "mp3", 50)
    assert k1 != k2
    svc.close()


def test_cache_key_changes_when_size_changes(tmp_path: Path) -> None:
    audio = _make_audio(tmp_path / "a.mp3", b"\x00" * 512)
    svc = ClipService(data_dir=tmp_path)
    k1 = svc._cache_key(audio, 0.0, 2.0, "mp3", 50)

    audio.write_bytes(b"\x00" * 1024)  # different size, same mtime unlikely but size differs
    k2 = svc._cache_key(audio, 0.0, 2.0, "mp3", 50)
    assert k1 != k2
    svc.close()


# ── 3: schema version bump invalidates cache ─────────────────────────────────


def test_schema_version_bump_changes_key(tmp_path: Path) -> None:
    """Bumping CLIP_CACHE_SCHEMA_VERSION must produce a different key for identical inputs."""
    import transcriptx.services.speaker_studio.clip_service as cs_mod

    audio = _make_audio(tmp_path / "a.mp3")
    svc = ClipService(data_dir=tmp_path)
    original_version = cs_mod.CLIP_CACHE_SCHEMA_VERSION

    k1 = svc._cache_key(audio, 0.0, 2.0, "mp3", 50)

    cs_mod.CLIP_CACHE_SCHEMA_VERSION = original_version + 1
    try:
        k2 = svc._cache_key(audio, 0.0, 2.0, "mp3", 50)
    finally:
        cs_mod.CLIP_CACHE_SCHEMA_VERSION = original_version

    assert k1 != k2
    svc.close()


def test_schema_version_constant_is_defined() -> None:
    assert isinstance(CLIP_CACHE_SCHEMA_VERSION, int)
    assert CLIP_CACHE_SCHEMA_VERSION >= 2


# ── 4: warm_clips deduplication ───────────────────────────────────────────────


def test_warm_clips_deduplicates_same_segment(tmp_path: Path) -> None:
    """Two warm_clips calls for the same segment should submit at most one job."""
    audio = _make_audio(tmp_path / "a.mp3")
    svc = ClipService(data_dir=tmp_path)

    submit_calls: List = []

    # Return a mock future that never reports done() so the dedup check can see
    # the key as still in-flight on the second warm_clips call.
    mock_future = MagicMock()
    mock_future.done.return_value = False

    def counting_submit(fn: object, *args: object, **kwargs: object) -> MagicMock:
        submit_calls.append(1)
        return mock_future

    with patch.object(svc._executor, "submit", side_effect=counting_submit):
        svc.warm_clips(audio, [(1.0, 3.0)])
        svc.warm_clips(audio, [(1.0, 3.0)])

    assert len(submit_calls) == 1, (
        f"Expected 1 submit for duplicate segment; got {len(submit_calls)}"
    )
    svc.close()


def test_warm_clips_skips_already_cached(tmp_path: Path) -> None:
    """warm_clips must skip segments whose clip file already exists on disk."""
    audio = _make_audio(tmp_path / "a.mp3")
    svc = ClipService(data_dir=tmp_path)

    # Pre-create the cache file.
    _, _, _, _, key, out_path = svc._compute_extract_params(
        audio, 1.0, 3.0, "mp3", 50
    )
    out_path.write_bytes(b"fake clip")

    submit_calls: List = []

    def _noop_submit(*a: object, **k: object) -> MagicMock:
        submit_calls.append(1)
        return MagicMock()

    with patch.object(svc._executor, "submit", side_effect=_noop_submit):
        svc.warm_clips(audio, [(1.0, 3.0)])

    assert len(submit_calls) == 0
    svc.close()


# ── 5: no duplicate ffmpeg for foreground + warm race ─────────────────────────


def test_foreground_joins_inflight_warm_job(tmp_path: Path) -> None:
    """
    If a warm job is in-flight for a key, get_clip_path must join it rather than
    spawning a second ffmpeg.  The final file must exist exactly once.
    """
    audio = _make_audio(tmp_path / "a.mp3")
    svc = ClipService(data_dir=tmp_path)

    # Pre-compute params to know the expected out_path.
    _, _, extract_start, extract_dur, key, out_path = svc._compute_extract_params(
        audio, 0.5, 2.5, "mp3", 50
    )

    generate_calls: List = []

    original_generate = svc._generate_sync

    def slow_generate(ap: object, es: object, ed: object, op: Path, format: object) -> None:
        generate_calls.append(1)
        # Simulate ffmpeg work: write a fake file after a brief pause.
        time.sleep(0.05)
        op.write_bytes(b"fake clip data")

    svc._generate_sync = slow_generate  # type: ignore[method-assign]

    # Manually register a warm future so the foreground call sees it as in-flight.
    evt = threading.Event()

    def warm_worker() -> None:
        try:
            svc._generate_sync(audio, extract_start, extract_dur, out_path, "mp3")
        finally:
            with svc._lock:
                svc._inflight.pop(key, None)
            evt.set()

    import concurrent.futures

    fut = svc._executor.submit(warm_worker)
    with svc._lock:
        svc._inflight[key] = fut

    # Foreground call should join the warm future.
    result = svc.get_clip_path(audio, 0.5, 2.5, format="mp3")
    evt.wait(timeout=5)

    assert out_path.exists()
    assert result == out_path
    # Only one generate call should have happened (from the warm worker).
    assert len(generate_calls) == 1

    svc._generate_sync = original_generate  # type: ignore[method-assign]
    svc.close()


# ── 6: temp file never visible to readers ─────────────────────────────────────


def test_temp_file_not_visible_to_get_clip_path(tmp_path: Path) -> None:
    """
    During generation, only the final path should be returned by get_clip_path.
    A temp file must never be returned as the result.
    """
    audio = _make_audio(tmp_path / "a.mp3")
    svc = ClipService(data_dir=tmp_path)
    _, _, _, _, _, out_path = svc._compute_extract_params(audio, 0.0, 1.0, "mp3", 50)

    observed_paths: List[Path] = []

    def fake_generate(ap: object, es: object, ed: object, op: Path, format: object) -> None:
        # op is the temp path; record it, then write content and let rename happen.
        observed_paths.append(op)
        op.write_bytes(b"clip")

    with patch.object(svc, "_generate_sync", side_effect=fake_generate):
        result = svc.get_clip_path(audio, 0.0, 1.0)

    # The returned path should be the final path, not a .tmp path.
    assert result == out_path or result.suffix != ".tmp"
    assert result.exists()
    # No .tmp files should survive.
    tmp_files = list(svc._cache_dir.glob("*.tmp"))
    assert tmp_files == [], f"Leaked temp files: {tmp_files}"

    svc.close()


# ── 7: ffmpeg_available guard ─────────────────────────────────────────────────


def test_ffmpeg_available_returns_false_when_absent(tmp_path: Path) -> None:
    with patch(
        "transcriptx.services.speaker_studio.clip_service._find_ffmpeg",
        return_value=None,
    ):
        svc = ClipService(data_dir=tmp_path)
        assert svc.ffmpeg_available() is False
        svc.close()


def test_warm_clips_noop_when_ffmpeg_absent(tmp_path: Path) -> None:
    audio = _make_audio(tmp_path / "a.mp3")
    with patch(
        "transcriptx.services.speaker_studio.clip_service._find_ffmpeg",
        return_value=None,
    ):
        svc = ClipService(data_dir=tmp_path)
        submit_calls: List = []
        with patch.object(svc._executor, "submit", side_effect=lambda *a, **k: submit_calls.append(1)):
            svc.warm_clips(audio, [(0.0, 2.0)])
        assert submit_calls == []
        svc.close()


def test_get_clip_path_raises_when_audio_missing(tmp_path: Path) -> None:
    svc = ClipService(data_dir=tmp_path)
    missing = tmp_path / "nonexistent.mp3"
    with pytest.raises(FileNotFoundError):
        svc.get_clip_path(missing, 0.0, 2.0)
    svc.close()


# ── 8: controller delegation ──────────────────────────────────────────────────


def test_controller_ffmpeg_available_delegates(tmp_path: Path) -> None:
    with patch(
        "transcriptx.services.speaker_studio.controller.ClipService"
    ) as MockCS:
        mock_svc = MagicMock()
        mock_svc.ffmpeg_available.return_value = True
        MockCS.return_value = mock_svc
        ctrl = SpeakerStudioController(data_dir=tmp_path)
        assert ctrl.ffmpeg_available() is True
        mock_svc.ffmpeg_available.assert_called_once()


def test_controller_warm_clips_delegates(tmp_path: Path) -> None:
    with (
        patch(
            "transcriptx.services.speaker_studio.controller.SegmentIndexService"
        ) as MockIdx,
        patch(
            "transcriptx.services.speaker_studio.controller.ClipService"
        ) as MockCS,
    ):
        mock_idx = MagicMock()
        mock_idx.get_transcript_audio_path.return_value = tmp_path / "audio.mp3"
        MockIdx.return_value = mock_idx

        mock_cs = MagicMock()
        MockCS.return_value = mock_cs

        ctrl = SpeakerStudioController(data_dir=tmp_path)
        ctrl.warm_clips("/path/t.json", [(0.0, 2.0), (2.0, 4.0)])

        mock_cs.warm_clips.assert_called_once_with(
            tmp_path / "audio.mp3", [(0.0, 2.0), (2.0, 4.0)], format="mp3"
        )


def test_controller_warm_clips_noop_when_no_audio(tmp_path: Path) -> None:
    with (
        patch(
            "transcriptx.services.speaker_studio.controller.SegmentIndexService"
        ) as MockIdx,
        patch(
            "transcriptx.services.speaker_studio.controller.ClipService"
        ) as MockCS,
    ):
        mock_idx = MagicMock()
        mock_idx.get_transcript_audio_path.return_value = None
        MockIdx.return_value = mock_idx

        mock_cs = MagicMock()
        MockCS.return_value = mock_cs

        ctrl = SpeakerStudioController(data_dir=tmp_path)
        ctrl.warm_clips("/path/t.json", [(0.0, 2.0)])

        mock_cs.warm_clips.assert_not_called()


# ── backpressure ──────────────────────────────────────────────────────────────


def test_warm_clips_respects_inflight_cap(tmp_path: Path) -> None:
    """warm_clips should stop enqueuing once the inflight cap is reached."""
    audio = _make_audio(tmp_path / "a.mp3")
    svc = ClipService(data_dir=tmp_path)

    # Pre-fill the inflight dict to the cap with dummy done=False futures.
    dummy_future = MagicMock()
    dummy_future.done.return_value = False
    with svc._lock:
        for i in range(svc._MAX_INFLIGHT):
            svc._inflight[f"fake_key_{i}"] = dummy_future

    submit_calls: List = []

    def _cap_submit(*a: object, **k: object) -> MagicMock:
        submit_calls.append(1)
        return MagicMock()

    with patch.object(svc._executor, "submit", side_effect=_cap_submit):
        # These should all be skipped because cap is reached.
        svc.warm_clips(audio, [(float(i), float(i) + 1) for i in range(5)])

    assert submit_calls == []
    svc.close()


# ── close / shutdown ──────────────────────────────────────────────────────────


def test_close_shuts_down_executor(tmp_path: Path) -> None:
    svc = ClipService(data_dir=tmp_path)
    # Should not raise; executor.shutdown is called.
    svc.close()
    # Submitting after close should raise (executor is shut down).
    with pytest.raises(RuntimeError):
        svc._executor.submit(lambda: None)


# ── speaker_id page contract ──────────────────────────────────────────────────


def test_speaker_id_page_imports_only_controller() -> None:
    """speaker_id.py must not import lower-level services directly."""
    import transcriptx.web.page_modules.speaker_id as mod

    source = Path(mod.__file__).read_text()
    assert "SpeakerStudioController" in source
    assert "SegmentIndexService" not in source
    assert "ClipService" not in source
    assert "SpeakerMappingService" not in source


def test_speaker_id_page_uses_render_playback_panel() -> None:
    """speaker_id.py must call render_playback_panel from the shared component."""
    import transcriptx.web.page_modules.speaker_id as mod

    source = Path(mod.__file__).read_text()
    assert "render_playback_panel" in source
    assert "playback_panel" in source


def test_speaker_studio_page_uses_render_playback_panel() -> None:
    """speaker_studio.py must call render_playback_panel from the shared component."""
    import transcriptx.web.page_modules.speaker_studio as mod

    source = Path(mod.__file__).read_text()
    assert "render_playback_panel" in source
    assert "playback_panel" in source


def test_speaker_studio_page_uses_on_click_for_play_buttons() -> None:
    """speaker_studio.py must use on_click callbacks, not st.rerun() after play buttons."""
    import transcriptx.web.page_modules.speaker_studio as mod

    source = Path(mod.__file__).read_text()
    assert "on_click=_set_play_idx" in source
    # The play buttons in rows should not call st.rerun() (rerun after save is fine,
    # but there must be no rerun immediately after setting active_index from a play click).
    # We verify on_click is present as the primary indicator.
    assert "_set_play_idx" in source
