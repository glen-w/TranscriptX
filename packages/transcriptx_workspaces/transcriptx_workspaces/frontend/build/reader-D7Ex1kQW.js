import { F as w, P as v } from "./constants-dt4zPgAn.js";
const x = /* @__PURE__ */ new WeakMap();
function h(t, e) {
  const r = t.querySelector(e);
  if (!r) throw new Error(`Missing element: ${e}`);
  return r;
}
function k(t, e) {
  let r = null;
  for (let n = 0; n < t.length; n++) {
    const o = t[n], i = n === t.length - 1;
    if (e >= o.start && (i ? e <= o.end : e < o.end)) {
      if (r = o.index, o.mode !== "karaoke")
        return { segmentIndex: r, wordIndex: null };
      for (let s = 0; s < o.words.length; s++) {
        const d = o.words[s];
        if (d.t0 != null && d.t1 != null && e >= d.t0 && e < d.t1)
          return { segmentIndex: r, wordIndex: s };
      }
      return { segmentIndex: r, wordIndex: null };
    }
  }
  return { segmentIndex: r, wordIndex: null };
}
function E(t, e) {
  if (!e.show_unnamed && t.named === !1)
    return !1;
  const r = (e.search_text || "").trim().toLowerCase();
  return r ? `${t.speaker} ${t.text}`.toLowerCase().includes(r) : !0;
}
function C(t, e) {
  if (t.length <= 300)
    return { start: 0, end: t.length };
  const r = e != null ? t.findIndex((s) => s.index === e) : 0, n = r >= 0 ? r : 0, i = Math.max(0, n - 40), l = Math.min(t.length, i + 80);
  return { start: i, end: l };
}
function T(t, e, r) {
  const n = h(r, ".tx-reader-caption");
  if (e.protocol_version !== v || e.frontend_build_id !== w) {
    n.textContent = "Reader workspace build mismatch — reload the page.";
    return;
  }
  if (!e.audio_ready || !e.audio_url) {
    n.textContent = e.unavailable_reason === "no_audio" ? "No audio file for this transcript." : e.unavailable_reason === "media_route_off" ? "Full-file playback requires loopback host (127.0.0.1)." : "Playback unavailable.";
    return;
  }
  const o = `${e.audio_url}\0${e.audio_fingerprint ?? ""}`;
  t.lastSrcKey !== o && (t.audio.src = e.audio_url, t.lastSrcKey = o), e.word_timing_omitted ? n.textContent = "Word highlight omitted — transcript payload too large. Segment highlight only." : e.segments.some((i) => i.mode === "karaoke") ? n.textContent = "Click a timed word to seek. Playhead stays in the player." : n.textContent = "Word timings missing or incomplete — highlighting the whole segment (no invented timings).";
}
function y(t, e, r, n) {
  const { segmentIndex: o, wordIndex: i } = k(e.segments, r);
  if (t.segmentEls.forEach((l, s) => {
    const d = o !== null && s === o;
    l.classList.toggle("tx-reader-turn--active", d), l.querySelectorAll(".tx-reader-word").forEach((c, a) => {
      var m;
      c.classList.remove("tx-reader-word--active", "tx-reader-word--spoken"), d && ((m = e.segments.find((u) => u.index === s)) == null ? void 0 : m.mode) === "karaoke" && (i !== null && a === i ? c.classList.add("tx-reader-word--active") : i !== null && a < i && c.classList.add("tx-reader-word--spoken"));
    });
  }), o !== null && o !== t.lastActiveIndex) {
    t.lastActiveIndex = o;
    const l = t.segmentEls.get(o), s = h(n, ".tx-reader-scroll");
    if (l && s) {
      const d = l.offsetTop, f = d + l.offsetHeight;
      (d < s.scrollTop || f > s.scrollTop + s.clientHeight) && l.scrollIntoView({ block: "nearest" });
    }
  }
}
function I(t, e, r) {
  var d;
  const n = h(r, ".tx-reader-scroll"), o = h(r, ".tx-reader-status"), i = e.jump_index ?? t.lastActiveIndex ?? ((d = e.segments[0]) == null ? void 0 : d.index) ?? null, { start: l, end: s } = C(e.segments, i);
  n.replaceChildren(), t.segmentEls.clear(), e.segments.length > 300 ? o.textContent = `Showing turns ${l + 1}–${s} of ${e.segments.length}` : o.textContent = "";
  for (let f = l; f < s; f++) {
    const c = e.segments[f], a = document.createElement("div");
    a.className = "tx-reader-turn", a.dataset.index = String(c.index), E(c, e) || a.classList.add("tx-reader-hidden");
    const m = document.createElement("div");
    m.className = "tx-reader-turn-head", m.textContent = `${c.speaker} · ${c.start.toFixed(1)}s`, a.appendChild(m);
    const u = document.createElement("div");
    u.className = "tx-reader-turn-body", c.mode === "karaoke" && c.words.length ? c.words.forEach((g, _) => {
      const p = document.createElement("span");
      p.className = "tx-reader-word", p.textContent = g.t, g.t0 != null ? p.addEventListener("click", () => {
        t.audio.currentTime = g.t0, t.audio.play().catch(() => {
        });
      }) : p.addEventListener("click", () => {
        t.audio.currentTime = c.start;
      }), u.appendChild(p), _ < c.words.length - 1 && u.appendChild(document.createTextNode(" "));
    }) : (u.textContent = c.text, u.addEventListener("click", () => {
      t.audio.currentTime = c.start, t.audio.play().catch(() => {
      });
    })), a.appendChild(u), n.appendChild(a), t.segmentEls.set(c.index, a);
  }
}
function b(t, e, r) {
  if (e.jump_epoch === t.lastJumpEpoch) return;
  t.lastJumpEpoch = e.jump_epoch;
  const n = e.jump_index;
  if (n == null) return;
  const o = e.segments.find((l) => l.index === n);
  if (!o) return;
  const i = t.segmentEls.get(n);
  i && i.scrollIntoView({ block: "center" }), e.autoplay_jump && (t.audio.currentTime = o.start, t.audio.play().catch(() => {
  }));
}
function L(t, e) {
  e.addEventListener("keydown", (r) => {
    const n = r, o = n.target;
    if (o.tagName === "INPUT" || o.tagName === "TEXTAREA") return;
    const i = e.__txReaderData;
    if (i) {
      if (n.code === "Space" && (n.preventDefault(), t.audio.paused ? t.audio.play().catch(() => {
      }) : t.audio.pause()), n.key === "j" || n.key === "ArrowDown") {
        const l = t.audio.currentTime, s = i.segments.find((d) => d.start > l + 0.05);
        s && (t.audio.currentTime = s.start);
      }
      if (n.key === "k" || n.key === "ArrowUp") {
        const l = t.audio.currentTime;
        let s = null;
        for (const d of i.segments)
          d.start < l - 0.05 && (s = d);
        s && (t.audio.currentTime = s.start);
      }
    }
  });
}
function A(t, e) {
  const r = {
    wired: !0,
    audio: e,
    lastSrcKey: null,
    lastJumpEpoch: -1,
    lastActiveIndex: null,
    segmentEls: /* @__PURE__ */ new Map()
  };
  return e.addEventListener("timeupdate", () => {
    const n = t.__txReaderData;
    n && y(r, n, e.currentTime, t);
  }), r;
}
const $ = (t) => {
  var l;
  const { parentElement: e, data: r } = t, n = e, o = ((l = n.querySelector) == null ? void 0 : l.call(n, ".tx-reader-root")) || n;
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
  applyAudioSrcKey: (t, e) => {
    const r = `${e.audio_url ?? ""}\0${e.audio_fingerprint ?? ""}`;
    return { key: r, changed: t.lastSrcKey !== r };
  }
};
export {
  R as __test,
  $ as default,
  k as pickActiveHighlight
};
