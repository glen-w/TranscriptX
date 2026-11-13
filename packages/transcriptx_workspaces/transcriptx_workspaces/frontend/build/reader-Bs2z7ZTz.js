import { F as w, i as v, P as E } from "./dom-_ymrU_C4.js";
const x = /* @__PURE__ */ new WeakMap();
function h(e, t) {
  const r = e.querySelector(t);
  if (!r) throw new Error(`Missing element: ${t}`);
  return r;
}
function y(e, t) {
  let r = null;
  for (let n = 0; n < e.length; n++) {
    const o = e[n], i = n === e.length - 1;
    if (t >= o.start && (i ? t <= o.end : t < o.end)) {
      if (r = o.index, o.mode !== "karaoke")
        return { segmentIndex: r, wordIndex: null };
      for (let l = 0; l < o.words.length; l++) {
        const c = o.words[l];
        if (c.t0 != null && c.t1 != null && t >= c.t0 && t < c.t1)
          return { segmentIndex: r, wordIndex: l };
      }
      return { segmentIndex: r, wordIndex: null };
    }
  }
  return { segmentIndex: r, wordIndex: null };
}
function C(e, t) {
  if (!t.show_unnamed && e.named === !1)
    return !1;
  const r = (t.search_text || "").trim().toLowerCase();
  return r ? `${e.speaker} ${e.text}`.toLowerCase().includes(r) : !0;
}
function T(e, t) {
  if (e.length <= 300)
    return { start: 0, end: e.length };
  const r = t != null ? e.findIndex((l) => l.index === t) : 0, n = r >= 0 ? r : 0, i = Math.max(0, n - 40), s = Math.min(e.length, i + 80);
  return { start: i, end: s };
}
function I(e, t, r) {
  const n = h(r, ".tx-reader-caption");
  if (t.protocol_version !== E || t.frontend_build_id !== w) {
    n.textContent = "Reader workspace build mismatch — reload the page.";
    return;
  }
  if (!t.audio_ready || !t.audio_url) {
    e.audio.hidden = !0, n.textContent = t.unavailable_reason === "no_audio" ? "No audio file for this transcript." : t.unavailable_reason === "media_route_off" ? "Full-file playback requires loopback host (127.0.0.1)." : "Playback unavailable.";
    return;
  }
  e.audio.hidden = !1;
  const o = `${t.audio_url}\0${t.audio_fingerprint ?? ""}`;
  e.lastSrcKey !== o && (e.audio.src = t.audio_url, e.lastSrcKey = o), t.word_timing_omitted ? n.textContent = "Word highlight omitted — transcript payload too large. Segment highlight only." : t.segments.some((i) => i.mode === "karaoke") ? n.textContent = "Click a timed word to seek. Playhead stays in the player." : n.textContent = "Word timings missing or incomplete — highlighting the whole segment (no invented timings).";
}
function k(e, t, r, n) {
  const { segmentIndex: o, wordIndex: i } = y(t.segments, r);
  if (e.segmentEls.forEach((s, l) => {
    const c = o !== null && l === o;
    s.classList.toggle("tx-reader-turn--active", c), s.querySelectorAll(".tx-reader-word").forEach((d, a) => {
      var m;
      d.classList.remove("tx-reader-word--active", "tx-reader-word--spoken"), c && ((m = t.segments.find((u) => u.index === l)) == null ? void 0 : m.mode) === "karaoke" && (i !== null && a === i ? d.classList.add("tx-reader-word--active") : i !== null && a < i && d.classList.add("tx-reader-word--spoken"));
    });
  }), o !== null && o !== e.lastActiveIndex) {
    e.lastActiveIndex = o;
    const s = e.segmentEls.get(o), l = h(n, ".tx-reader-scroll");
    if (s && l) {
      const c = s.offsetTop, f = c + s.offsetHeight;
      (c < l.scrollTop || f > l.scrollTop + l.clientHeight) && s.scrollIntoView({ block: "nearest" });
    }
  }
}
function b(e, t, r) {
  var c;
  const n = h(r, ".tx-reader-scroll"), o = h(r, ".tx-reader-status"), i = t.jump_index ?? e.lastActiveIndex ?? ((c = t.segments[0]) == null ? void 0 : c.index) ?? null, { start: s, end: l } = T(t.segments, i);
  n.replaceChildren(), e.segmentEls.clear(), t.segments.length > 300 ? o.textContent = `Showing turns ${s + 1}–${l} of ${t.segments.length}` : o.textContent = "";
  for (let f = s; f < l; f++) {
    const d = t.segments[f], a = document.createElement("div");
    a.className = "tx-reader-turn", a.dataset.index = String(d.index), C(d, t) || a.classList.add("tx-reader-hidden");
    const m = document.createElement("div");
    m.className = "tx-reader-turn-head", m.textContent = `${d.speaker} · ${d.start.toFixed(1)}s`, a.appendChild(m);
    const u = document.createElement("div");
    u.className = "tx-reader-turn-body", d.mode === "karaoke" && d.words.length ? d.words.forEach((g, _) => {
      const p = document.createElement("span");
      p.className = "tx-reader-word", p.textContent = g.t, g.t0 != null ? p.addEventListener("click", () => {
        e.audio.currentTime = g.t0, e.audio.play().catch(() => {
        });
      }) : p.addEventListener("click", () => {
        e.audio.currentTime = d.start;
      }), u.appendChild(p), _ < d.words.length - 1 && u.appendChild(document.createTextNode(" "));
    }) : (u.textContent = d.text, u.addEventListener("click", () => {
      e.audio.currentTime = d.start, e.audio.play().catch(() => {
      });
    })), a.appendChild(u), n.appendChild(a), e.segmentEls.set(d.index, a);
  }
}
function L(e, t, r) {
  if (t.jump_epoch === e.lastJumpEpoch) return;
  e.lastJumpEpoch = t.jump_epoch;
  const n = t.jump_index;
  if (n == null) return;
  const o = t.segments.find((s) => s.index === n);
  if (!o) return;
  const i = e.segmentEls.get(n);
  i && i.scrollIntoView({ block: "center" }), t.autoplay_jump && (e.audio.currentTime = o.start, e.audio.play().catch(() => {
  }));
}
function $(e, t) {
  t.addEventListener("keydown", (r) => {
    const n = r;
    if (v(n.target)) return;
    const o = t.__txReaderData;
    if (o) {
      if (n.code === "Space" && (n.preventDefault(), e.audio.paused ? e.audio.play().catch(() => {
      }) : e.audio.pause()), n.key === "j" || n.key === "ArrowDown") {
        const i = e.audio.currentTime, s = o.segments.find((l) => l.start > i + 0.05);
        s && (e.audio.currentTime = s.start);
      }
      if (n.key === "k" || n.key === "ArrowUp") {
        const i = e.audio.currentTime;
        let s = null;
        for (const l of o.segments)
          l.start < i - 0.05 && (s = l);
        s && (e.audio.currentTime = s.start);
      }
    }
  });
}
function S(e, t) {
  const r = {
    wired: !0,
    audio: t,
    lastSrcKey: null,
    lastJumpEpoch: -1,
    lastActiveIndex: null,
    segmentEls: /* @__PURE__ */ new Map()
  };
  return t.addEventListener("timeupdate", () => {
    const n = e.__txReaderData;
    n && k(r, n, t.currentTime, e);
  }), r;
}
const R = (e) => {
  var s;
  const { parentElement: t, data: r } = e, n = t, o = ((s = n.querySelector) == null ? void 0 : s.call(n, ".tx-reader-root")) || n;
  let i = x.get(n);
  if (!i) {
    const l = h(o, ".tx-reader-audio");
    i = S(o, l), x.set(n, i), $(i, o);
  }
  return o.__txReaderData = r, I(i, r, o), b(i, r, o), L(i, r), k(i, r, i.audio.currentTime, o), () => {
    x.delete(n);
  };
}, N = {
  FRONTEND_BUILD_ID: w,
  pickActiveHighlight: y,
  applyAudioSrcKey: (e, t) => {
    const r = `${t.audio_url ?? ""}\0${t.audio_fingerprint ?? ""}`;
    return { key: r, changed: e.lastSrcKey !== r };
  }
};
export {
  N as __test,
  R as default,
  y as pickActiveHighlight
};
