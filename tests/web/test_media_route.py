"""Tests for Theme D loopback media route."""

from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path

import pytest

from transcriptx.web.media_route import MediaRoute, get_media_route


def test_mint_rejects_missing_and_directory(tmp_path: Path) -> None:
    route = MediaRoute()
    missing = tmp_path / "nope.mp3"
    with pytest.raises(ValueError):
        route.mint(missing)
    with pytest.raises(ValueError):
        route.mint(tmp_path)


def test_get_serves_bytes_and_range(tmp_path: Path) -> None:
    audio = tmp_path / "clip.mp3"
    audio.write_bytes(b"0123456789abcdef")
    route = MediaRoute()
    token = route.mint(audio)
    url = route.audio_url(token)
    assert route._httpd is not None
    assert route._httpd.server_address[0] == "127.0.0.1"

    with urllib.request.urlopen(url) as resp:
        assert resp.read() == audio.read_bytes()

    req = urllib.request.Request(
        url, headers={"Range": "bytes=0-3"}, method="GET"
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 206
        assert resp.headers["Content-Range"] == "bytes 0-3/16"
        assert resp.read() == b"0123"


def test_tokens_are_isolated(tmp_path: Path) -> None:
    a = tmp_path / "a.mp3"
    b = tmp_path / "b.mp3"
    a.write_bytes(b"aaa")
    b.write_bytes(b"bbb")
    route = MediaRoute()
    ta = route.mint(a)
    tb = route.mint(b)
    with urllib.request.urlopen(route.audio_url(ta)) as resp:
        assert resp.read() == b"aaa"
    with urllib.request.urlopen(route.audio_url(tb)) as resp:
        assert resp.read() == b"bbb"


def test_invalid_paths_404(tmp_path: Path) -> None:
    audio = tmp_path / "x.mp3"
    audio.write_bytes(b"x")
    route = MediaRoute()
    token = route.mint(audio)
    base = route.base_url
    for bad in (
        f"{base}/audio/{token}/extra",
        f"{base}/audio/../{token}",
    ):
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(bad)
        assert exc.value.code in (400, 404)


def test_stale_token_after_file_change(tmp_path: Path) -> None:
    audio = tmp_path / "mut.mp3"
    audio.write_bytes(b"old-content-here")
    route = MediaRoute()
    token = route.mint(audio)
    audio.write_bytes(b"new")
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(route.audio_url(token))
    assert exc.value.code == 404


def test_singleton_get_media_route() -> None:
    assert get_media_route() is get_media_route()
