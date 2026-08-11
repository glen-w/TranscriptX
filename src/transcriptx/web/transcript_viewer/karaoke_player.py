"""Browser-local karaoke clip player for the Transcript viewer (Theme D).

Playhead stays in the iframe — never streamed to Python via setStateValue.
Word highlight and seek-from-word run against clip-relative timings from
``karaoke_timing.build_karaoke_clip_model``.
"""

from __future__ import annotations

import base64
import json
from typing import Any, Mapping, Optional

import streamlit as st
import streamlit.components.v1 as components

from transcriptx.core.utils.logger import get_logger
from transcriptx.services.speaker_studio.controller import SpeakerStudioController
from transcriptx.services.speaker_studio.segment_index import SegmentInfo
from transcriptx.web.components.playback_panel import (
    PlaybackContext,
    _sanitised_clip_warning,
    render_active_clip,
)
from transcriptx.web.transcript_viewer.karaoke_timing import (
    KaraokeClipModel,
    build_karaoke_clip_model,
    karaoke_words_payload,
)
from transcriptx.web.workspaces.playback_host import PlaybackHostCapabilities

logger = get_logger()

_KARAOKE_CSS = """
:root {
  --tx-k-bg: #12161c;
  --tx-k-panel: #1a212b;
  --tx-k-ink: #e8eef7;
  --tx-k-muted: #9aa7b8;
  --tx-k-accent: #3d8fd1;
  --tx-k-active: #f0c14a;
  --tx-k-active-bg: rgba(240, 193, 74, 0.18);
  --tx-k-spoken: rgba(232, 238, 247, 0.55);
  --tx-k-border: rgba(140, 160, 185, 0.28);
  font-family: "IBM Plex Sans", "Source Sans 3", "Segoe UI", sans-serif;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: transparent;
  color: var(--tx-k-ink);
}
.tx-karaoke {
  background: linear-gradient(165deg, var(--tx-k-panel) 0%, var(--tx-k-bg) 70%);
  border: 1px solid var(--tx-k-border);
  border-radius: 0.55rem;
  padding: 0.65rem 0.8rem 0.75rem;
}
.tx-karaoke-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem 0.75rem;
  align-items: baseline;
  margin: 0 0 0.45rem;
  font-size: 0.82rem;
  color: var(--tx-k-muted);
}
.tx-karaoke-speaker {
  color: var(--tx-k-accent);
  font-weight: 650;
}
.tx-karaoke-mode {
  margin-left: auto;
  font-size: 0.72rem;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}
.tx-karaoke audio {
  width: 100%;
  height: 2rem;
  margin: 0 0 0.55rem;
}
.tx-karaoke-text {
  margin: 0;
  line-height: 1.55;
  font-size: 1.02rem;
  white-space: pre-wrap;
  word-break: break-word;
}
.tx-karaoke-word {
  border-radius: 0.2rem;
  padding: 0.02rem 0.05rem;
  transition: color 80ms linear, background-color 80ms linear;
}
.tx-karaoke-word[data-timed="1"] {
  cursor: pointer;
}
.tx-karaoke-word[data-timed="1"]:hover {
  background: rgba(61, 143, 209, 0.18);
}
.tx-karaoke-word.is-spoken {
  color: var(--tx-k-spoken);
}
.tx-karaoke-word.is-active {
  color: var(--tx-k-ink);
  background: var(--tx-k-active-bg);
  box-shadow: inset 0 -2px 0 var(--tx-k-active);
  font-weight: 600;
}
.tx-karaoke-text.is-segment-active {
  background: var(--tx-k-active-bg);
  border-radius: 0.3rem;
  padding: 0.2rem 0.35rem;
}
.tx-karaoke-hint {
  margin: 0.45rem 0 0;
  font-size: 0.75rem;
  color: var(--tx-k-muted);
}
"""

_KARAOKE_JS = r"""
(function () {
  const root = document.getElementById("tx-karaoke-root");
  const payloadEl = document.getElementById("tx-karaoke-payload");
  if (!root || !payloadEl) return;
  let payload;
  try {
    payload = JSON.parse(payloadEl.textContent || "{}");
  } catch (e) {
    root.textContent = "Karaoke payload error.";
    return;
  }

  const audio = document.createElement("audio");
  audio.controls = true;
  audio.preload = "auto";
  audio.setAttribute("data-testid", "tx-karaoke-audio");
  if (payload.clip_b64) {
    audio.src = "data:audio/mpeg;base64," + payload.clip_b64;
  }

  const meta = document.createElement("div");
  meta.className = "tx-karaoke-meta";
  const speaker = document.createElement("span");
  speaker.className = "tx-karaoke-speaker";
  speaker.textContent = payload.speaker || "Unknown";
  const range = document.createElement("span");
  range.textContent = payload.range_label || "";
  const mode = document.createElement("span");
  mode.className = "tx-karaoke-mode";
  mode.textContent = payload.mode === "karaoke" ? "Word sync" : "Segment sync";
  meta.append(speaker, range, mode);

  const textEl = document.createElement("p");
  textEl.className = "tx-karaoke-text";
  textEl.setAttribute("data-testid", "tx-karaoke-text");

  const words = Array.isArray(payload.words) ? payload.words : [];
  const wordEls = [];
  words.forEach(function (w, idx) {
    if (idx > 0) textEl.appendChild(document.createTextNode(" "));
    const span = document.createElement("span");
    span.className = "tx-karaoke-word";
    span.textContent = w.t || "";
    const timed = typeof w.t0 === "number" && typeof w.t1 === "number";
    span.dataset.timed = timed ? "1" : "0";
    if (timed) {
      span.dataset.t0 = String(w.t0);
      span.dataset.t1 = String(w.t1);
      span.title = "Seek to this word";
      span.addEventListener("click", function () {
        try {
          audio.currentTime = Math.max(0, Number(w.t0) || 0);
          if (audio.paused) {
            audio.play().catch(function () {});
          }
        } catch (err) {}
      });
    }
    textEl.appendChild(span);
    wordEls.push({ el: span, t0: timed ? w.t0 : null, t1: timed ? w.t1 : null });
  });
  if (!words.length) {
    textEl.textContent = payload.text || "";
  }

  const hint = document.createElement("p");
  hint.className = "tx-karaoke-hint";
  hint.textContent =
    payload.mode === "karaoke"
      ? "Follow-along word highlight · click a timed word to seek"
      : "Word timings unavailable — segment-level highlight while playing";

  root.append(meta, audio, textEl, hint);

  let lastActive = -1;
  function paint(t) {
    if (payload.mode !== "karaoke") {
      if (!audio.paused && !audio.ended) {
        textEl.classList.add("is-segment-active");
      } else {
        textEl.classList.remove("is-segment-active");
      }
      return;
    }
    let containing = -1;
    let lastDone = -1;
    for (let i = 0; i < wordEls.length; i++) {
      const w = wordEls[i];
      if (w.t0 == null || w.t1 == null) continue;
      if (t + 1e-4 >= w.t0 && t < w.t1) containing = i;
      if (t + 1e-4 >= w.t1) lastDone = i;
    }
    const active = containing >= 0 ? containing : lastDone;
    for (let i = 0; i < wordEls.length; i++) {
      const w = wordEls[i];
      const el = w.el;
      el.classList.toggle("is-active", i === active && containing === i);
      el.classList.toggle(
        "is-spoken",
        w.t1 != null && t + 1e-4 >= w.t1 && i !== containing
      );
    }
    lastActive = active;
  }

  let raf = 0;
  function tick() {
    paint(audio.currentTime || 0);
    raf = window.requestAnimationFrame(tick);
  }
  function startLoop() {
    if (!raf) raf = window.requestAnimationFrame(tick);
  }
  function stopLoop() {
    if (raf) {
      window.cancelAnimationFrame(raf);
      raf = 0;
    }
    paint(audio.currentTime || 0);
  }

  audio.addEventListener("play", startLoop);
  audio.addEventListener("playing", startLoop);
  audio.addEventListener("pause", stopLoop);
  audio.addEventListener("ended", function () {
    stopLoop();
    if (payload.mode === "karaoke") {
      for (let i = 0; i < wordEls.length; i++) {
        wordEls[i].el.classList.remove("is-active");
      }
    } else {
      textEl.classList.remove("is-segment-active");
    }
  });
  audio.addEventListener("seeked", function () {
    paint(audio.currentTime || 0);
  });

  if (payload.autoplay) {
    const p = audio.play();
    if (p && typeof p.catch === "function") p.catch(function () {});
  }
})();
"""


def _format_range_label(start: float, end: float) -> str:
    def _fmt(v: float) -> str:
        if v < 60:
            return f"{v:.1f}s"
        m = int(v // 60)
        s = v - 60 * m
        return f"{m}:{s:04.1f}"

    return f"{_fmt(start)} – {_fmt(end)}"


def estimate_karaoke_frame_height(model: KaraokeClipModel) -> int:
    """Estimate iframe height from text length (capped)."""
    chars = max(len(model.text), 1)
    lines = max(2, (chars // 64) + 1)
    return int(min(420, max(150, 110 + lines * 26)))


def build_karaoke_html(
    model: KaraokeClipModel,
    *,
    clip_b64: str,
    autoplay: bool = True,
) -> str:
    """Return a self-contained HTML document for ``components.html``."""
    payload = {
        "mode": model.mode,
        "speaker": model.speaker,
        "text": model.text,
        "range_label": _format_range_label(model.clip_start, model.clip_end),
        "autoplay": bool(autoplay),
        "clip_b64": clip_b64,
        "words": karaoke_words_payload(model),
    }
    payload_json = json.dumps(payload, ensure_ascii=False)
    # Prevent </script> breakouts from transcript text inside JSON.
    payload_json = payload_json.replace("<", "\\u003c").replace(">", "\\u003e")
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<style>{_KARAOKE_CSS}</style></head><body>"
        '<div class="tx-karaoke" id="tx-karaoke-root" '
        'data-testid="tx-karaoke-root"></div>'
        '<script type="application/json" id="tx-karaoke-payload">'
        f"{payload_json}</script>"
        f"<script>{_KARAOKE_JS}</script>"
        "</body></html>"
    )


def render_karaoke_player_html(
    model: KaraokeClipModel,
    *,
    clip_bytes: bytes,
    autoplay: bool = True,
) -> None:
    """Mount the karaoke iframe player."""
    clip_b64 = base64.b64encode(clip_bytes).decode("ascii")
    html = build_karaoke_html(model, clip_b64=clip_b64, autoplay=autoplay)
    components.html(html, height=estimate_karaoke_frame_height(model), scrolling=True)


def render_transcript_karaoke_clip(
    controller: SpeakerStudioController,
    transcript_path: str,
    segment: Optional[SegmentInfo],
    segment_dict: Optional[Mapping[str, Any]],
    *,
    autoplay: bool = False,
    playback_context: Optional[PlaybackContext] = None,
) -> Optional[KaraokeClipModel]:
    """
    Render Theme D karaoke (or segment fallback) for the active Transcript clip.

    When ``segment`` is None, mounts the shared idle silent player so layout
    does not jump on first play. Returns the karaoke model when a clip rendered.
    """
    if segment is None:
        render_active_clip(
            controller,
            transcript_path,
            None,
            autoplay=False,
            playback_context=playback_context,
        )
        return None

    source = (
        segment_dict
        if isinstance(segment_dict, Mapping)
        else {
            "text": segment.text,
            "start": segment.start,
            "end": segment.end,
            "speaker": segment.speaker,
        }
    )
    model = build_karaoke_clip_model(
        source,
        clip_start=segment.start,
        clip_end=segment.end,
    )
    try:
        resolved_audio = (
            playback_context.audio_path if playback_context is not None else None
        )
        clip_bytes = controller.get_clip_bytes(
            transcript_path,
            segment.start,
            segment.end,
            format="mp3",
            audio_path=resolved_audio,
        )
        if not clip_bytes:
            st.warning(_sanitised_clip_warning())
            return None
        if model.mode == "segment":
            st.caption(
                "_Word timings missing or incomplete — highlighting the whole "
                "segment while this clip plays (no invented timings)._"
            )
        else:
            st.caption(
                "_Karaoke word highlight · click a timed word to seek. "
                "Playhead stays in the player._"
            )
        render_karaoke_player_html(model, clip_bytes=clip_bytes, autoplay=autoplay)
        return model
    except Exception:
        logger.warning(
            "Karaoke clip render failed transcript=%s segment_index=%s start=%s end=%s",
            transcript_path,
            segment.index,
            segment.start,
            segment.end,
            exc_info=True,
        )
        st.warning(_sanitised_clip_warning())
        return None


class TranscriptKaraokeHost:
    """Concrete PlaybackHost for the Transcript karaoke surface.

    Local clock is iframe-owned; Python only exposes last-known capabilities.
    """

    def __init__(self) -> None:
        self._capabilities = PlaybackHostCapabilities()
        self._last_seek_ms = 0

    def play_clip(self, clip_id: str, src: str) -> None:
        # Browser owns playback; Python only swaps payloads on rerun.
        del clip_id, src

    def pause(self) -> None:
        return None

    def seek_ms(self, position_ms: int) -> None:
        self._last_seek_ms = max(0, int(position_ms))

    def local_current_time_ms(self) -> int:
        # Intentionally not mirrored from the browser.
        return int(self._last_seek_ms)

    def capabilities(self) -> PlaybackHostCapabilities:
        return self._capabilities

    def bind_model(self, model: Optional[KaraokeClipModel]) -> None:
        if model is None:
            self._capabilities = PlaybackHostCapabilities()
        else:
            self._capabilities = model.capabilities
