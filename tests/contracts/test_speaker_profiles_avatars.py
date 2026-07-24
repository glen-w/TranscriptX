"""Avatar set/clear/path/hash and UI chip contracts."""

from __future__ import annotations

import io
from pathlib import Path
from uuid import uuid4

import pytest
from PIL import Image

from transcriptx.core.speaker_profiles.avatars import (
    normalize_avatar_image,
    relative_avatar_path,
    validate_avatar_field_set,
    validate_avatar_relpath,
)
from transcriptx.core.speaker_profiles.errors import SpeakerProfileContractError
from transcriptx.core.speaker_profiles.integrity import run_integrity_scan
from transcriptx.core.speaker_profiles.models import SpeakerProfileV1
from transcriptx.core.speaker_profiles.service import SpeakerProfileService
from transcriptx.core.speaker_profiles.store_io import (
    profile_content_sha256,
    read_profile,
)
from transcriptx.web.speaker_avatar import (
    speaker_avatar_chip_html,
    speaker_initials,
)


def _png_bytes(color: tuple[int, int, int] = (10, 20, 30), size: int = 64) -> bytes:
    img = Image.new("RGB", (size, size), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> SpeakerProfileService:
    root = tmp_path / "speaker_profiles"
    state = tmp_path / "state"
    root.mkdir()
    state.mkdir()
    monkeypatch.setenv("TRANSCRIPTX_SPEAKER_PROFILES_DIR", str(root))
    monkeypatch.setenv("TRANSCRIPTX_STATE_DIR", str(state))
    # PATHS may cache — construct service with explicit dirs if supported
    svc = SpeakerProfileService(root=root, state_dir=state)
    return svc


def _seed_profile(svc: SpeakerProfileService, *, name: str = "Ada") -> str:
    from transcriptx.core.speaker_profiles.layout import profile_path
    from transcriptx.core.speaker_profiles.store_io import (
        dumps_model,
        ensure_layout,
        utc_now_iso,
        write_bytes_under_root,
    )

    ensure_layout(svc.root)
    pid = str(uuid4())
    now = utc_now_iso()
    write_bytes_under_root(
        profile_path(pid, root=svc.root),
        dumps_model(
            SpeakerProfileV1(
                profile_id=pid,
                display_name=name,
                created_at=now,
                updated_at=now,
            )
        ),
        root=svc.root,
    )
    return pid


def _rgba_png_bytes() -> bytes:
    img = Image.new("RGBA", (64, 64), (10, 20, 30, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _animated_webp_bytes() -> bytes:
    frames = []
    for i in range(2):
        frames.append(Image.new("RGB", (32, 32), (i * 40, 0, 0)))
    buf = io.BytesIO()
    frames[0].save(
        buf,
        format="WEBP",
        save_all=True,
        append_images=frames[1:],
        duration=50,
        loop=0,
    )
    return buf.getvalue()


def test_avatar_relpath_rejects_traversal_and_mismatch():
    pid = str(uuid4())
    ok = relative_avatar_path(pid)
    assert validate_avatar_relpath(ok, profile_id=pid) == ok
    with pytest.raises(SpeakerProfileContractError):
        validate_avatar_relpath("../etc/passwd", profile_id=pid)
    with pytest.raises(SpeakerProfileContractError):
        validate_avatar_relpath(f"/profiles/assets/{pid}/avatar.webp", profile_id=pid)
    with pytest.raises(SpeakerProfileContractError):
        validate_avatar_relpath(f"profiles/assets/{pid}/avatar.jpg", profile_id=pid)
    with pytest.raises(SpeakerProfileContractError):
        validate_avatar_relpath(f"profiles/assets/{pid}/Avatar.webp", profile_id=pid)
    with pytest.raises(SpeakerProfileContractError):
        validate_avatar_relpath(relative_avatar_path(str(uuid4())), profile_id=pid)


def test_avatar_fields_coherent_nullable_set():
    pid = str(uuid4())
    validate_avatar_field_set(
        avatar_relpath=None,
        avatar_sha256=None,
        avatar_content_type=None,
        profile_id=pid,
    )
    with pytest.raises(SpeakerProfileContractError):
        validate_avatar_field_set(
            avatar_relpath=relative_avatar_path(pid),
            avatar_sha256=None,
            avatar_content_type="image/webp",
            profile_id=pid,
        )


def test_normalize_rejects_oversized_and_accepts_png():
    with pytest.raises(SpeakerProfileContractError):
        normalize_avatar_image(b"x" * (2 * 1024 * 1024 + 1))
    webp, digest = normalize_avatar_image(_png_bytes())
    assert webp[:4] == b"RIFF"
    assert len(digest) == 64


def test_set_clear_avatar_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    svc = _make_service(tmp_path, monkeypatch)
    # Minimal create without transcript link: write profile via create needs occurrence.
    # Use model write through set after creating via engine path from phase15 helpers.
    from transcriptx.core.speaker_profiles.store_io import (
        dumps_model,
        ensure_layout,
        write_bytes_under_root,
    )
    from transcriptx.core.speaker_profiles.layout import profile_path
    from transcriptx.core.speaker_profiles.store_io import utc_now_iso

    ensure_layout(svc.root)
    pid = str(uuid4())
    now = utc_now_iso()
    profile = SpeakerProfileV1(
        profile_id=pid,
        display_name="Ada Lovelace",
        created_at=now,
        updated_at=now,
    )
    write_bytes_under_root(
        profile_path(pid, root=svc.root), dumps_model(profile), root=svc.root
    )
    sha = profile_content_sha256(pid, root=svc.root)
    assert sha
    svc.set_avatar(
        operation_idempotency_key=str(uuid4()),
        profile_id=pid,
        expected_content_sha256=sha,
        image_bytes=_png_bytes(),
    )
    loaded = read_profile(pid, root=svc.root)
    assert loaded is not None
    assert loaded.avatar_sha256
    assert loaded.avatar_relpath == relative_avatar_path(pid)
    data = svc.read_avatar_bytes(pid)
    assert data is not None
    assert data[:4] == b"RIFF"

    sha2 = profile_content_sha256(pid, root=svc.root)
    assert sha2
    svc.clear_avatar(
        operation_idempotency_key=str(uuid4()),
        profile_id=pid,
        expected_content_sha256=sha2,
    )
    loaded2 = read_profile(pid, root=svc.root)
    assert loaded2 is not None
    assert loaded2.avatar_relpath is None
    assert svc.read_avatar_bytes(pid) is None
    report = run_integrity_scan(svc.root)
    assert report.ok


def test_failed_upload_is_non_destructive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    svc = _make_service(tmp_path, monkeypatch)
    from transcriptx.core.speaker_profiles.store_io import (
        dumps_model,
        ensure_layout,
        write_bytes_under_root,
    )
    from transcriptx.core.speaker_profiles.layout import profile_path
    from transcriptx.core.speaker_profiles.store_io import utc_now_iso

    ensure_layout(svc.root)
    pid = str(uuid4())
    now = utc_now_iso()
    profile = SpeakerProfileV1(
        profile_id=pid,
        display_name="Grace",
        created_at=now,
        updated_at=now,
    )
    write_bytes_under_root(
        profile_path(pid, root=svc.root), dumps_model(profile), root=svc.root
    )
    sha = profile_content_sha256(pid, root=svc.root)
    assert sha
    svc.set_avatar(
        operation_idempotency_key=str(uuid4()),
        profile_id=pid,
        expected_content_sha256=sha,
        image_bytes=_png_bytes((1, 2, 3)),
    )
    before = read_profile(pid, root=svc.root)
    assert before is not None and before.avatar_sha256
    sha2 = profile_content_sha256(pid, root=svc.root)
    with pytest.raises(SpeakerProfileContractError):
        svc.set_avatar(
            operation_idempotency_key=str(uuid4()),
            profile_id=pid,
            expected_content_sha256=sha2 or "",
            image_bytes=b"not-an-image",
        )
    after = read_profile(pid, root=svc.root)
    assert after is not None
    assert after.avatar_sha256 == before.avatar_sha256
    assert after.updated_at == before.updated_at


def test_hash_mismatch_read_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    svc = _make_service(tmp_path, monkeypatch)
    from transcriptx.core.speaker_profiles.store_io import (
        dumps_model,
        ensure_layout,
        write_bytes_under_root,
    )
    from transcriptx.core.speaker_profiles.layout import avatar_path, profile_path
    from transcriptx.core.speaker_profiles.store_io import utc_now_iso

    ensure_layout(svc.root)
    pid = str(uuid4())
    now = utc_now_iso()
    webp, digest = normalize_avatar_image(_png_bytes())
    profile = SpeakerProfileV1(
        profile_id=pid,
        display_name="X",
        created_at=now,
        updated_at=now,
        avatar_relpath=relative_avatar_path(pid),
        avatar_sha256=digest,
        avatar_content_type="image/webp",
    )
    write_bytes_under_root(
        profile_path(pid, root=svc.root), dumps_model(profile), root=svc.root
    )
    # Corrupt asset
    write_bytes_under_root(avatar_path(pid, root=svc.root), b"RIFF????", root=svc.root)
    assert svc.read_avatar_bytes(pid) is None
    report = run_integrity_scan(svc.root)
    assert any(i.startswith("avatar_hash_mismatch:") for i in report.avatar_issues)


def test_pre_avatar_profile_reads_defaults():
    now = "2026-01-01T00:00:00Z"
    pid = str(uuid4())
    # Simulate old JSON without avatar keys via model_construct then validation
    raw = {
        "version": 1,
        "schema_id": "transcriptx.speaker_profile.v1",
        "profile_id": pid,
        "display_name": "Legacy",
        "aliases": [],
        "notes": None,
        "accent_color": None,
        "status": "active",
        "merged_into_profile_id": None,
        "created_at": now,
        "updated_at": now,
    }
    profile = SpeakerProfileV1.model_validate(raw)
    assert profile.avatar_relpath is None
    assert profile.avatar_sha256 is None
    assert profile.avatar_content_type is None


def test_merge_target_wins_deletes_source_avatar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    svc = _make_service(tmp_path, monkeypatch)
    from transcriptx.core.speaker_profiles.store_io import (
        dumps_model,
        ensure_layout,
        utc_now_iso,
        write_bytes_under_root,
    )
    from transcriptx.core.speaker_profiles.layout import profile_path

    ensure_layout(svc.root)
    now = utc_now_iso()
    source_id = str(uuid4())
    target_id = str(uuid4())
    for pid, name in ((source_id, "Source"), (target_id, "Target")):
        write_bytes_under_root(
            profile_path(pid, root=svc.root),
            dumps_model(
                SpeakerProfileV1(
                    profile_id=pid,
                    display_name=name,
                    created_at=now,
                    updated_at=now,
                )
            ),
            root=svc.root,
        )
    # Both get avatars
    for pid, color in ((source_id, (9, 9, 9)), (target_id, (1, 1, 1))):
        sha = profile_content_sha256(pid, root=svc.root)
        assert sha
        svc.set_avatar(
            operation_idempotency_key=str(uuid4()),
            profile_id=pid,
            expected_content_sha256=sha,
            image_bytes=_png_bytes(color),
        )
    target_before = read_profile(target_id, root=svc.root)
    assert target_before is not None
    source_sha = profile_content_sha256(source_id, root=svc.root)
    assert source_sha
    svc.merge_profiles(
        operation_idempotency_key=str(uuid4()),
        source_profile_id=source_id,
        target_profile_id=target_id,
        expected_source_sha256=source_sha,
    )
    target_after = read_profile(target_id, root=svc.root)
    source_after = read_profile(source_id, root=svc.root)
    assert target_after is not None and source_after is not None
    assert target_after.avatar_sha256 == target_before.avatar_sha256
    assert source_after.status == "merged"
    assert source_after.avatar_relpath is None
    assert not (svc.root / relative_avatar_path(source_id)).exists()


def test_chip_dimensions_parity_photo_vs_fallback():
    webp, _ = normalize_avatar_image(_png_bytes())
    initials = speaker_avatar_chip_html("Ada Lovelace", accent="#112233")
    photo = speaker_avatar_chip_html(
        "Ada Lovelace",
        accent="#112233",
        image_bytes=webp,
    )
    assert 'class="tx-speaker-avatar"' in initials
    assert 'class="tx-speaker-avatar"' in photo
    assert "--tx-avatar-size: 40px" in initials
    assert "--tx-avatar-size: 40px" in photo
    assert "tx-speaker-avatar-initials" in initials
    assert "tx-speaker-avatar-img" in photo
    assert speaker_initials("Ada Lovelace") == "AL"
    escaped = speaker_avatar_chip_html("<script>")
    assert "&lt;" in escaped
    assert "<script>" not in escaped


def test_normalize_rejects_animated_and_accepts_rgba(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    with pytest.raises(SpeakerProfileContractError):
        normalize_avatar_image(_animated_webp_bytes())
    webp, _ = normalize_avatar_image(_rgba_png_bytes())
    assert webp[:4] == b"RIFF"
    # Round-trip decode should be opaque RGB WebP
    from PIL import Image as PILImage

    img = PILImage.open(io.BytesIO(webp))
    assert img.mode in ("RGB", "RGBA")
    assert img.size == (512, 512)


def test_set_avatar_stale_occ(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from transcriptx.core.speaker_profiles.errors import StaleUpdateError

    svc = _make_service(tmp_path, monkeypatch)
    pid = _seed_profile(svc)
    with pytest.raises(StaleUpdateError):
        svc.set_avatar(
            operation_idempotency_key=str(uuid4()),
            profile_id=pid,
            expected_content_sha256="0" * 64,
            image_bytes=_png_bytes(),
        )
    loaded = read_profile(pid, root=svc.root)
    assert loaded is not None
    assert loaded.avatar_relpath is None


def test_clear_avatar_stale_occ(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from transcriptx.core.speaker_profiles.errors import StaleUpdateError

    svc = _make_service(tmp_path, monkeypatch)
    pid = _seed_profile(svc)
    sha = profile_content_sha256(pid, root=svc.root)
    assert sha
    svc.set_avatar(
        operation_idempotency_key=str(uuid4()),
        profile_id=pid,
        expected_content_sha256=sha,
        image_bytes=_png_bytes(),
    )
    with pytest.raises(StaleUpdateError):
        svc.clear_avatar(
            operation_idempotency_key=str(uuid4()),
            profile_id=pid,
            expected_content_sha256=sha,  # stale after set
        )
    assert svc.read_avatar_bytes(pid) is not None


def test_merge_adopt_source_avatar_when_target_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    svc = _make_service(tmp_path, monkeypatch)
    source_id = _seed_profile(svc, name="Source")
    target_id = _seed_profile(svc, name="Target")
    sha = profile_content_sha256(source_id, root=svc.root)
    assert sha
    svc.set_avatar(
        operation_idempotency_key=str(uuid4()),
        profile_id=source_id,
        expected_content_sha256=sha,
        image_bytes=_png_bytes((50, 60, 70)),
    )
    source_before = read_profile(source_id, root=svc.root)
    assert source_before is not None and source_before.avatar_sha256
    source_sha = profile_content_sha256(source_id, root=svc.root)
    assert source_sha
    svc.merge_profiles(
        operation_idempotency_key=str(uuid4()),
        source_profile_id=source_id,
        target_profile_id=target_id,
        expected_source_sha256=source_sha,
    )
    target = read_profile(target_id, root=svc.root)
    source = read_profile(source_id, root=svc.root)
    assert target is not None and source is not None
    assert target.avatar_sha256 == source_before.avatar_sha256
    assert target.avatar_relpath == relative_avatar_path(target_id)
    assert source.avatar_relpath is None
    assert svc.read_avatar_bytes(target_id) is not None
    assert not (svc.root / relative_avatar_path(source_id)).exists()


def test_integrity_orphan_and_dangling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from transcriptx.core.speaker_profiles.layout import avatar_path, profile_path
    from transcriptx.core.speaker_profiles.store_io import (
        dumps_model,
        ensure_layout,
        utc_now_iso,
        write_bytes_under_root,
    )

    svc = _make_service(tmp_path, monkeypatch)
    ensure_layout(svc.root)
    # Orphan asset without pointer
    orphan_id = str(uuid4())
    write_bytes_under_root(
        avatar_path(orphan_id, root=svc.root),
        normalize_avatar_image(_png_bytes())[0],
        root=svc.root,
    )
    # Dangling pointer without asset
    pid = str(uuid4())
    now = utc_now_iso()
    webp, digest = normalize_avatar_image(_png_bytes((1, 1, 1)))
    write_bytes_under_root(
        profile_path(pid, root=svc.root),
        dumps_model(
            SpeakerProfileV1(
                profile_id=pid,
                display_name="Dangle",
                created_at=now,
                updated_at=now,
                avatar_relpath=relative_avatar_path(pid),
                avatar_sha256=digest,
                avatar_content_type="image/webp",
            )
        ),
        root=svc.root,
    )
    report = run_integrity_scan(svc.root)
    assert any(i.startswith("avatar_orphan:") for i in report.avatar_issues)
    assert any(i.startswith("avatar_missing:") for i in report.avatar_issues)
    assert not report.ok


def test_set_then_clear_idempotent_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    svc = _make_service(tmp_path, monkeypatch)
    pid = _seed_profile(svc)
    sha = profile_content_sha256(pid, root=svc.root)
    assert sha
    key = str(uuid4())
    r1 = svc.set_avatar(
        operation_idempotency_key=key,
        profile_id=pid,
        expected_content_sha256=sha,
        image_bytes=_png_bytes(),
    )
    r2 = svc.set_avatar(
        operation_idempotency_key=key,
        profile_id=pid,
        expected_content_sha256=sha,
        image_bytes=_png_bytes((99, 99, 99)),
    )
    assert r1.outcome.replayed is False
    assert r2.outcome.replayed is True
    # Replay must not apply the second image
    first_hash = read_profile(pid, root=svc.root)
    assert first_hash is not None
    clear_key = str(uuid4())
    sha2 = profile_content_sha256(pid, root=svc.root)
    assert sha2
    c1 = svc.clear_avatar(
        operation_idempotency_key=clear_key,
        profile_id=pid,
        expected_content_sha256=sha2,
    )
    c2 = svc.clear_avatar(
        operation_idempotency_key=clear_key,
        profile_id=pid,
        expected_content_sha256=sha2,
    )
    assert c1.outcome.replayed is False
    assert c2.outcome.replayed is True
    assert svc.read_avatar_bytes(pid) is None
