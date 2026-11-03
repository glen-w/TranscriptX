import { F as w, P as v } from "./constants-dt4zPgAn.js";
const x = /* @__PURE__ */ new WeakMap();
function h(e, t) {
  const r = e.querySelector(t);
  if (!r) throw new Error(`Missing element: ${t}`);
  return r;
}
function k(e, t) {
  let r = null;
  for (let n = 0; n < e.length; n++) {
    const o = e[n], i = n === e.length - 1;
    if (t >= o.start && (i ? t <= o.end : t < o.end)) {
      if (r = o.index, o.mode !== "karaoke")
        return { segmentIndex: r, wordIndex: null };
      for (let s = 0; s < o.words.length; s++) {
        const d = o.words[s];
        if (d.t0 != null && d.t1 != null && t >= d.t0 && t < d.t1)
          return { segmentIndex: r, wordIndex: s };
      }
      return { segmentIndex: r, wordIndex: null };
    }
  }
  return { segmentIndex: r, wordIndex: null };
}
function E(e, t) {
  if (!t.show_unnamed && e.named === !1)
    return !1;
  const r = (t.search_text || "").trim().toLowerCase();
  return r ? `${e.speaker} ${e.text}`.toLowerCase().includes(r) : !0;
}
function C(e, t) {
  if (e.length <= 300)
    return { start: 0, end: e.length };
  const r = t != null ? e.findIndex((s) => s.index === t) : 0, n = r >= 0 ? r : 0, i = Math.max(0, n - 40), l = Math.min(e.length, i + 80);
  return { start: i, end: l };
}
function T(e, t, r) {
  const n = h(r, ".tx-reader-caption");
  if (t.protocol_version !== v || t.frontend_build_id !== w) {
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
function y(e, t, r, n) {
  const { segmentIndex: o, wordIndex: i } = k(t.segments, r);
  if (e.segmentEls.forEach((l, s) => {
    const d = o !== null && s === o;
    l.classList.toggle("tx-reader-turn--active", d), l.querySelectorAll(".tx-reader-word").forEach((c, a) => {
      var m;
      c.classList.remove("tx-reader-word--active", "tx-reader-word--spoken"), d && ((m = t.segments.find((u) => u.index === s)) == null ? void 0 : m.mode) === "karaoke" && (i !== null && a === i ? c.classList.add("tx-reader-word--active") : i !== null && a < i && c.classList.add("tx-reader-word--spoken"));
    });
  }), o !== null && o !== e.lastActiveIndex) {
    e.lastActiveIndex = o;
    const l = e.segmentEls.get(o), s = h(n, ".tx-reader-scroll");
    if (l && s) {
      const d = l.offsetTop, f = d + l.offsetHeight;
      (d < s.scrollTop || f > s.scrollTop + s.clientHeight) && l.scrollIntoView({ block: "nearest" });
    }
  }
}
function I(e, t, r) {
  var d;
  const n = h(r, ".tx-reader-scroll"), o = h(r, ".tx-reader-status"), i = t.jump_index ?? e.lastActiveIndex ?? ((d = t.segments[0]) == null ? void 0 : d.index) ?? null, { start: l, end: s } = C(t.segments, i);
  n.replaceChildren(), e.segmentEls.clear(), t.segments.length > 300 ? o.textContent = `Showing turns ${l + 1}–${s} of ${t.segments.length}` : o.textContent = "";
  for (let f = l; f < s; f++) {
    const c = t.segments[f], a = document.createElement("div");
    a.className = "tx-reader-turn", a.dataset.index = String(c.index), E(c, t) || a.classList.add("tx-reader-hidden");
    const m = document.createElement("div");
    m.className = "tx-reader-turn-head", m.textContent = `${c.speaker} · ${c.start.toFixed(1)}s`, a.appendChild(m);
    const u = document.createElement("div");
    u.className = "tx-reader-turn-body", c.mode === "karaoke" && c.words.length ? c.words.forEach((g, _) => {
      const p = document.createElement("span");
      p.className = "tx-reader-word", p.textContent = g.t, g.t0 != null ? p.addEventListener("click", () => {
        e.audio.currentTime = g.t0, e.audio.play().catch(() => {
        });
      }) : p.addEventListener("click", () => {
        e.audio.currentTime = c.start;
      }), u.appendChild(p), _ < c.words.length - 1 && u.appendChild(document.createTextNode(" "));
    }) : (u.textContent = c.text, u.addEventListener("click", () => {
      e.audio.currentTime = c.start, e.audio.play().catch(() => {
      });
    })), a.appendChild(u), n.appendChild(a), e.segmentEls.set(c.index, a);
  }
}
function b(e, t, r) {
  if (t.jump_epoch === e.lastJumpEpoch) return;
  e.lastJumpEpoch = t.jump_epoch;
  const n = t.jump_index;
  if (n == null) return;
  const o = t.segments.find((l) => l.index === n);
  if (!o) return;
  const i = e.segmentEls.get(n);
  i && i.scrollIntoView({ block: "center" }), t.autoplay_jump && (e.audio.currentTime = o.start, e.audio.play().catch(() => {
  }));
}
function L(e, t) {
  t.addEventListener("keydown", (r) => {
    const n = r, o = n.target;
    if (o.tagName === "INPUT" || o.tagName === "TEXTAREA") return;
    const i = t.__txReaderData;
    if (i) {
      if (n.code === "Space" && (n.preventDefault(), e.audio.paused ? e.audio.play().catch(() => {
      }) : e.audio.pause()), n.key === "j" || n.key === "ArrowDown") {
        const l = e.audio.currentTime, s = i.segments.find((d) => d.start > l + 0.05);
        s && (e.audio.currentTime = s.start);
      }
      if (n.key === "k" || n.key === "ArrowUp") {
        const l = e.audio.currentTime;
        let s = null;
        for (const d of i.segments)
          d.start < l - 0.05 && (s = d);
        s && (e.audio.currentTime = s.start);
      }
    }
  });
}
function A(e, t) {
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
    n && y(r, n, t.currentTime, e);
  }), r;
}
const $ = (e) => {
  var l;
  const { parentElement: t, data: r } = e, n = t, o = ((l = n.querySelector) == null ? void 0 : l.call(n, ".tx-reader-root")) || n;
  let i = x.get(n);
  if (!i) {
    const s = h(o, ".tx-reader-audio");
    i = A(o, s), x.set(n, i), L(i, o);
  }
  return o.__txReaderData = r, T(i, r, o), I(i, r, o), b(i, r), y(i, r, i.audio.currentTime, o), () => {
    x.delete(n);
  };
}, R = {
  FRONTEND_BUILD_ID: w,
  pickActiveHighlight: k,
  applyAudioSrcKey: (e, t) => {
    const r = `${t.audio_url ?? ""}\0${t.audio_fingerprint ?? ""}`;
    return { key: r, changed: e.lastSrcKey !== r };
  }
};
export {
  R as __test,
  $ as default,
  k as pickActiveHighlight
};
