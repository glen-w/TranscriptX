"""Loopback-only HTTP media route for Theme D full-file playback (ClipTransport T3).

Serves registered audio files with Range support. Binds 127.0.0.1 only.
"""

from __future__ import annotations

import http.server
import mimetypes
import re
import secrets
import socketserver
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_MAX_REGISTRY = 32
_RANGE_RE = re.compile(r"^bytes=(\d+)-(\d*)$")

_ROUTE: Optional["MediaRoute"] = None
_ROUTE_LOCK = threading.Lock()


def loopback_host_allowed() -> bool:
    """True when Streamlit is expected to bind on loopback (media route may start)."""
    import os

    host = (os.environ.get("TRANSCRIPTX_HOST") or "127.0.0.1").strip().lower()
    if host in {"127.0.0.1", "localhost", "::1"}:
        return True
    if host.startswith("127."):
        return True
    return False


def _content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    mapping = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".mp4": "audio/mp4",
        ".ogg": "audio/ogg",
    }
    if suffix in mapping:
        return mapping[suffix]
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


@dataclass(frozen=True)
class _RegistryEntry:
    path: Path
    size: int
    mtime_ns: int


class MediaRoute:
    """Process-global loopback media server with token registry."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tokens: OrderedDict[str, _RegistryEntry] = OrderedDict()
        self._httpd: Optional[socketserver.TCPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._port: Optional[int] = None
        self._start_failed = False

    @property
    def available(self) -> bool:
        return self._httpd is not None and self._port is not None

    @property
    def base_url(self) -> str:
        if self._port is None:
            raise RuntimeError("media route not started")
        return f"http://127.0.0.1:{self._port}"

    def audio_url(self, token: str) -> str:
        return f"{self.base_url}/audio/{token}"

    def _ensure_started(self) -> bool:
        if self._httpd is not None:
            return True
        if self._start_failed:
            return False
        if not loopback_host_allowed():
            self._start_failed = True
            return False
        route = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                del format, args

            def do_GET(self) -> None:
                self._serve(method="GET")

            def do_HEAD(self) -> None:
                self._serve(method="HEAD")

            def _serve(self, *, method: str) -> None:
                if self.path.startswith("/audio/"):
                    parts = self.path.split("/")
                    if len(parts) != 3 or parts[0] != "" or parts[1] != "audio":
                        self.send_error(404)
                        return
                    token = parts[2]
                    if ".." in token or "/" in token or not token:
                        self.send_error(404)
                        return
                    entry = route._lookup(token)
                    if entry is None:
                        self.send_error(404)
                        return
                    try:
                        if not entry.path.is_file():
                            route._drop(token)
                            self.send_error(404)
                            return
                        st_ = entry.path.stat()
                        if st_.st_size != entry.size or st_.st_mtime_ns != entry.mtime_ns:
                            route._drop(token)
                            self.send_error(404)
                            return
                        size = entry.size
                    except OSError:
                        route._drop(token)
                        self.send_error(404)
                        return

                    range_header = self.headers.get("Range")
                    if range_header is None:
                        self.send_response(200)
                        self.send_header("Content-Type", _content_type(entry.path))
                        self.send_header("Content-Length", str(size))
                        self.send_header("Accept-Ranges", "bytes")
                        self.end_headers()
                        if method == "GET":
                            with entry.path.open("rb") as fh:
                                self.wfile.write(fh.read())
                        return

                    match = _RANGE_RE.match(range_header.strip())
                    if not match:
                        self.send_error(416)
                        return
                    start = int(match.group(1))
                    end_s = match.group(2)
                    if end_s:
                        end = int(end_s)
                    else:
                        end = size - 1
                    if start < 0 or end < start or start >= size:
                        self.send_error(416)
                        return
                    end = min(end, size - 1)
                    length = end - start + 1
                    self.send_response(206)
                    self.send_header("Content-Type", _content_type(entry.path))
                    self.send_header("Content-Length", str(length))
                    self.send_header(
                        "Content-Range", f"bytes {start}-{end}/{size}"
                    )
                    self.send_header("Accept-Ranges", "bytes")
                    self.end_headers()
                    if method == "GET":
                        with entry.path.open("rb") as fh:
                            fh.seek(start)
                            self.wfile.write(fh.read(length))
                    return

                self.send_error(404)

            def do_OPTIONS(self) -> None:
                self.send_error(405)

            def do_POST(self) -> None:
                self.send_error(405)

        try:
            httpd = socketserver.TCPServer(("127.0.0.1", 0), Handler)
            httpd.allow_reuse_address = True
            port = httpd.server_address[1]
            thread = threading.Thread(
                target=httpd.serve_forever, name="tx-media-route", daemon=True
            )
            thread.start()
            self._httpd = httpd
            self._thread = thread
            self._port = port
            return True
        except OSError:
            self._start_failed = True
            return False

    def mint(self, path: Path) -> str:
        resolved = path.resolve()
        if not resolved.is_file():
            raise ValueError("media route mint requires a regular file")
        st_ = resolved.stat()
        entry = _RegistryEntry(
            path=resolved, size=int(st_.st_size), mtime_ns=int(st_.st_mtime_ns)
        )
        if not self._ensure_started():
            raise RuntimeError("media route unavailable")
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._tokens[token] = entry
            while len(self._tokens) > _MAX_REGISTRY:
                self._tokens.popitem(last=False)
        return token

    def _lookup(self, token: str) -> Optional[_RegistryEntry]:
        with self._lock:
            return self._tokens.get(token)

    def _drop(self, token: str) -> None:
        with self._lock:
            self._tokens.pop(token, None)


def get_media_route() -> MediaRoute:
    global _ROUTE
    with _ROUTE_LOCK:
        if _ROUTE is None:
            _ROUTE = MediaRoute()
        return _ROUTE
