import { F as S, P as E } from "./constants-dt4zPgAn.js";
const K = 2, I = 5;
function L(t) {
  const e = t.filter(
    (n) => (n.mention_count ?? 0) >= K
  );
  return {
    head: e.slice(0, I),
    tail: e.slice(I)
  };
}
function w(t, e) {
  const n = document.createElement("li"), s = e.mention_count ? ` (${e.mention_count})` : "";
  n.textContent = `${e.display_name}${s}`, t.appendChild(n);
}
const b = /* @__PURE__ */ new WeakMap(), N = 8e6, W = 4, X = 200, Y = 3e3, z = 2;
function q() {
  return typeof crypto < "u" && "randomUUID" in crypto ? crypto.randomUUID().replace(/-/g, "") : `a${Date.now().toString(16)}${Math.random().toString(16).slice(2)}`;
}
function u(t, e) {
  const n = t.querySelector(e);
  if (!n) throw new Error(`Missing element: ${e}`);
  return n;
}
function A(t) {
  for (const e of t.blobUrls.values())
    URL.revokeObjectURL(e);
  t.blobUrls.clear(), t.blobBytes = 0;
}
function D(t, e, n, s) {
  const i = t.blobUrls.get(e);
  if (i) return i;
  try {
    const r = atob(n);
    if (t.blobBytes + r.length > s)
      return null;
    const o = new Uint8Array(r.length);
    for (let c = 0; c < r.length; c++) o[c] = r.charCodeAt(c);
    const a = URL.createObjectURL(new Blob([o], { type: "audio/mpeg" }));
    return t.blobUrls.set(e, a), t.blobBytes += r.length, a;
  } catch {
    return null;
  }
}
function x(t, e, n, s = {}, i = {}) {
  const r = !!i.mutating;
  if (r && t.mutating) return;
  if (e.protocol_version !== E || e.frontend_build_id !== S) {
    t.setTriggerValue("command", {
      protocol_version: E,
      frontend_build_id: S,
      action_id: q(),
      action_seq: ++t.actionSeq,
      transcript_id: e.transcript_id,
      transcript_revision: e.transcript_revision,
      expected_speaker_id: e.active_speaker_id,
      expected_mapping_revision: e.mapping_revision,
      audio_fingerprint: e.audio_fingerprint ?? null,
      action: "protocol_mismatch",
      payload: {
        got_protocol: e.protocol_version,
        got_build: e.frontend_build_id
      }
    });
    return;
  }
  r && (t.mutating = !0);
  const o = {
    protocol_version: E,
    frontend_build_id: S,
    action_id: q(),
    action_seq: ++t.actionSeq,
    transcript_id: e.transcript_id,
    transcript_revision: e.transcript_revision,
    expected_speaker_id: e.active_speaker_id,
    expected_mapping_revision: e.mapping_revision,
    audio_fingerprint: e.audio_fingerprint ?? null,
    action: n,
    payload: s
  };
  t.setTriggerValue("command", o), t.setStateValue("ack_seq", o.action_seq);
}
function k(t) {
  for (const e of t.retryTimers) window.clearTimeout(e);
  t.retryTimers = [], t.activeMissRetries = 0;
}
function G(t, e) {
  k(t), t.pendingPlay = null;
  const n = e.querySelector(".tx-sid-clip-status");
  n && (n.textContent = "");
}
function J(t) {
  return Math.min(Y, X * 2 ** t);
}
function y(t, e) {
  u(t, ".tx-sid-clip-status").textContent = e;
}
function T(t, e, n, s, i = {}) {
  if (!n.clip_b64) return !1;
  const r = D(t, n.clip_id, n.clip_b64, s);
  if (!r) return !1;
  const o = i.autoplay !== !1;
  if (t.audio.src !== r)
    t.audio.src = r;
  else if (o)
    try {
      t.audio.currentTime = 0;
    } catch {
    }
  return o ? (y(e, ""), t.audio.play().then(() => {
    y(e, "");
  }).catch((a) => {
    const c = a && typeof a == "object" && "name" in a ? String(a.name) : "";
    if (c !== "AbortError") {
      if (c === "NotAllowedError") {
        y(e, "Ready — click ▶ to play");
        return;
      }
      y(e, "Playback failed — click ▶ again.");
    }
  }), !0) : (y(e, "Ready — click ▶ to play"), !0);
}
function M(t, e, n) {
  const s = t.pendingPlay;
  if (!s) return;
  if (s.attempt >= W) {
    u(e, ".tx-sid-clip-status").textContent = "Clip still preparing — click ▶ again.", t.pendingPlay = null;
    return;
  }
  if (t.activeMissRetries >= z) return;
  const i = J(s.attempt);
  s.attempt += 1, t.activeMissRetries += 1;
  const r = window.setTimeout(() => {
    t.activeMissRetries = Math.max(0, t.activeMissRetries - 1);
    const o = t.pendingPlay, a = t.lastDataRef;
    !o || !a || o.clipId !== s.clipId || (u(e, ".tx-sid-clip-status").textContent = "Preparing clip…", x(t, a, "refresh_clips", {
      clip_id: o.clipId,
      start: o.start,
      end: o.end
    }), M(t, e));
  }, i);
  t.retryTimers.push(r);
}
function Q(t, e, n, s) {
  var o;
  const i = ((o = n.budgets) == null ? void 0 : o.max_blob_bytes) ?? N;
  if (T(t, e, s, i, { autoplay: !0 })) {
    k(t), t.pendingPlay = null;
    return;
  }
  const r = s.clip_status || "";
  if (r === "unavailable" || r === "too_large") {
    k(t), t.pendingPlay = null, y(
      e,
      r === "too_large" ? "Clip too large to load." : "Clip unavailable."
    );
    return;
  }
  k(t), t.pendingPlay = {
    clipId: s.clip_id,
    start: s.start,
    end: s.end,
    attempt: 0
  }, y(e, "Preparing clip…"), x(t, n, "enqueue_clip", {
    clip_id: s.clip_id,
    start: s.start,
    end: s.end
  }), M(t, e);
}
function U(t, e) {
  const n = t.samples || [], s = n.find((i) => i.clip_id === e.clipId);
  return s || n.find(
    (i) => Math.abs(i.start - e.start) < 1e-3 && Math.abs(i.end - e.end) < 1e-3
  );
}
function Z(t, e, n) {
  var o;
  const s = t.pendingPlay;
  if (!s) return;
  const i = U(n, s);
  if (!i) return;
  const r = ((o = n.budgets) == null ? void 0 : o.max_blob_bytes) ?? N;
  if (T(t, e, i, r, { autoplay: !0 })) {
    k(t), t.pendingPlay = null;
    return;
  }
  (i.clip_status === "unavailable" || i.clip_status === "too_large") && (k(t), t.pendingPlay = null, y(
    e,
    i.clip_status === "too_large" ? "Clip too large to load." : "Clip unavailable."
  ));
}
function B(t, e, n) {
  const s = u(t, ".tx-sid-speakers");
  s.replaceChildren();
  const i = n.optimisticSpeakerId ?? e.active_speaker_id;
  for (const r of e.speakers || []) {
    const o = document.createElement("button");
    o.type = "button", o.className = "tx-sid-speaker-btn", o.textContent = r.label, r.id === i && o.setAttribute("aria-current", "true"), o.addEventListener("click", () => {
      n.optimisticSpeakerId = r.id, x(n, e, "navigate_jump", {
        target_speaker_id: r.id
      }), B(t, e, n);
    }), s.appendChild(o);
  }
}
function ee(t, e, n) {
  const s = u(t, ".tx-sid-samples");
  s.replaceChildren();
  for (const i of e.samples || []) {
    const r = document.createElement("li");
    r.className = "tx-sid-sample";
    const o = document.createElement("button");
    o.type = "button", o.className = "tx-sid-sample-play", o.textContent = "▶", o.setAttribute("aria-label", "Play sample"), o.addEventListener("click", () => {
      Q(n, t, e, i);
    });
    const a = document.createElement("div");
    a.textContent = i.text || "", r.append(o, a), s.appendChild(r);
  }
}
function te(t, e, n) {
  const s = u(t, ".tx-sid-paging");
  s.replaceChildren();
  const i = e.paging;
  if (!i || i.shown >= i.total) {
    s.hidden = !0;
    return;
  }
  s.hidden = !1;
  const r = i.total - i.shown, o = Math.min(i.page_size, r), a = document.createElement("button");
  a.type = "button", a.className = "tx-sid-load-more", a.textContent = `Show ${o} more lines`, a.addEventListener("click", () => {
    x(n, e, "load_more_samples", { n: o });
  }), s.appendChild(a);
}
function R(t) {
  return t.mode === "existing" && t.profile_id ? `existing:${t.profile_id}` : t.mode || "none";
}
function O(t) {
  if (t.startsWith("existing:")) {
    const e = t.slice(9).trim() || null;
    return {
      link_mode: e ? "existing" : "none",
      profile_id: e,
      link_profile: !!e
    };
  }
  return t === "create" ? { link_mode: "create", profile_id: null, link_profile: !0 } : { link_mode: "none", profile_id: null, link_profile: !1 };
}
function V(t) {
  return t.trim().replace(/\s+/g, " ").toLocaleLowerCase();
}
function ne(t, e) {
  const n = [t.display_name || "", ...t.aliases || []].map(V);
  return n.some((s) => s === e) ? 0 : n.some((s) => s.startsWith(e)) ? 1 : 3;
}
function j(t, e) {
  const n = V(e), s = t.filter((c) => c.mode === "existing"), i = t.filter((c) => c.mode !== "existing"), r = s.map((c, f) => ({
    row: c,
    index: f,
    score: n ? ne(c, n) : 3
  })), o = r.filter((c) => n && c.score < 3).sort((c, f) => c.score - f.score || c.index - f.index).map((c) => c.row), a = r.filter((c) => !n || c.score >= 3).sort((c, f) => c.index - f.index).map((c) => c.row);
  return [...o, ...i, ...a];
}
function $(t, e, n) {
  const s = n.display_name || "";
  if (t.value = s, s) {
    if (!Array.from(e.options).some((r) => r.value === s)) {
      const r = document.createElement("option");
      r.value = s, r.textContent = n.label || s, e.appendChild(r);
    }
    e.value = s;
  }
  t.dispatchEvent(new Event("input", { bubbles: !0 }));
}
function F(t, e) {
  var m, C;
  const n = t.querySelector(".tx-sid-name-pick"), s = t.querySelector(".tx-sid-name-datalist"), i = t.querySelector(".tx-sid-name-hint"), r = t.querySelector(".tx-sid-roster"), o = t.querySelector(".tx-sid-roster-list");
  if (!n || !s || !i || !r || !o) return;
  const a = e.name_suggestions, c = ((m = a == null ? void 0 : a.by_speaker) == null ? void 0 : m[e.active_speaker_id]) || [];
  n.replaceChildren();
  const f = document.createElement("option");
  f.value = "", f.textContent = c.length ? "Suggested names…" : "No suggestions yet", n.appendChild(f), s.replaceChildren();
  for (const _ of c) {
    const h = document.createElement("option");
    h.value = _.display_name, h.textContent = _.label || _.display_name, n.appendChild(h);
    const v = document.createElement("option");
    v.value = _.display_name, s.appendChild(v);
  }
  const l = n.value, p = c.find((_) => _.display_name === l);
  p != null && p.quote ? i.textContent = p.quote : a != null && a.status_message && !c.length ? i.textContent = a.status_message : i.textContent = "";
  const { head: g, tail: d } = L((a == null ? void 0 : a.roster) || []);
  if (o.replaceChildren(), (C = r.querySelector(".tx-sid-roster-overflow")) == null || C.remove(), g.length || d.length) {
    r.hidden = !1;
    for (const _ of g)
      w(o, _);
    if (d.length) {
      const _ = document.createElement("details");
      _.className = "tx-sid-roster-overflow";
      const h = document.createElement("summary");
      h.className = "tx-sid-roster-overflow-summary", h.textContent = d.length === 1 ? "1 more" : `${d.length} more`, _.appendChild(h);
      const v = document.createElement("ul");
      v.className = "tx-sid-roster-overflow-list";
      for (const H of d)
        w(v, H);
      _.appendChild(v), r.appendChild(_);
    }
  } else
    r.hidden = !0;
}
function P(t, e) {
  var g;
  const n = u(t, ".tx-sid-link-select"), s = u(t, ".tx-sid-link-chip"), i = !!(e.link_profile_allowed ?? ((g = e.capabilities) == null ? void 0 : g.profile_link)), r = t.querySelector(".tx-sid-name-input"), o = (r == null ? void 0 : r.value) || e.draft_name || "", a = j(e.link_targets || [], o), c = n.value;
  n.replaceChildren();
  for (const d of a) {
    const m = document.createElement("option");
    m.value = R(d), m.textContent = d.label, d.is_default && (m.selected = !0), n.appendChild(m);
  }
  if (!a.length) {
    const d = document.createElement("option");
    d.value = "none", d.textContent = "Name only — this transcript", n.appendChild(d);
  }
  const f = Array.from(n.options).map((d) => d.value);
  if (c && f.includes(c))
    n.value = c;
  else {
    const d = a.find((m) => m.is_default);
    d && (n.value = R(d));
  }
  n.disabled = !i && f.every((d) => d === "none" || d === "");
  const l = a.find((d) => R(d) === n.value), p = [];
  l != null && l.detail && p.push(l.detail), l != null && l.duplicate_name_warning && p.push("A profile with this name already exists."), e.recipe_hint && p.push(e.recipe_hint), s.textContent = p.join(" ");
}
function ie(t, e, n) {
  var o, a;
  (n.lastTranscriptId !== e.transcript_id || n.lastSpeakerId !== e.active_speaker_id) && (G(n, t), n.lastTranscriptId = e.transcript_id, n.lastSpeakerId = e.active_speaker_id), u(t, ".tx-sid-title").textContent = `Speaker ${e.active_speaker_id}`;
  const s = u(t, ".tx-sid-status");
  s.textContent = ((o = e.ui) == null ? void 0 : o.status) || "", e.ack && e.ack.action_seq >= n.lastAckSeq && (n.lastAckSeq = e.ack.action_seq, e.ack.action_seq >= n.actionSeq - 0, (e.ack.status === "ok" || e.ack.status === "partial" || e.ack.status === "error" || e.ack.status === "rejected_stale" || e.ack.status === "rejected_protocol") && (n.mutating = !1, n.optimisticSpeakerId = null), e.ack.status === "rejected_protocol" && (s.textContent = e.ack.message || "Protocol mismatch — reload or use classic UI."));
  const i = u(t, ".tx-sid-name-input");
  document.activeElement !== i && (i.value = e.draft_name || ""), P(t, e), F(t, e);
  const r = !!((a = e.ui) != null && a.disabled || n.mutating);
  for (const c of [".tx-sid-save", ".tx-sid-ignore", ".tx-sid-prev", ".tx-sid-next"])
    u(t, c).disabled = r;
  B(t, e, n), ee(t, e, n), te(t, e, n), n.lastDataRef = e, Z(n, t, e);
}
function se(t, e, n) {
  const i = {
    wired: !0,
    audio: u(e, ".tx-sid-audio"),
    blobUrls: /* @__PURE__ */ new Map(),
    blobBytes: 0,
    lastAckSeq: 0,
    actionSeq: 0,
    mutating: !1,
    optimisticSpeakerId: null,
    retryTimers: [],
    pendingPlay: null,
    activeMissRetries: 0,
    lastTranscriptId: null,
    lastSpeakerId: null,
    handlers: {
      onSave: () => {
      },
      onIgnore: () => {
      },
      onPrev: () => {
      },
      onNext: () => {
      },
      onKey: () => {
      },
      onNameInput: () => {
      }
    },
    lastDataRef: null,
    setTriggerValue: n.setTriggerValue,
    setStateValue: n.setStateValue,
    host: t
  };
  (() => {
    i.handlers.onSave = () => {
      const l = i.lastDataRef;
      if (!l) return;
      const p = u(e, ".tx-sid-name-input").value.trim(), g = u(e, ".tx-sid-link-select").value, d = O(g);
      x(
        i,
        l,
        "save_name",
        {
          display_name: p,
          link_profile: d.link_profile,
          link_mode: d.link_mode,
          profile_id: d.profile_id
        },
        { mutating: !0 }
      );
    }, i.handlers.onIgnore = () => {
      const l = i.lastDataRef;
      l && x(i, l, "ignore_toggle", {}, { mutating: !0 });
    }, i.handlers.onPrev = () => {
      const l = i.lastDataRef;
      l && x(i, l, "navigate_prev");
    }, i.handlers.onNext = () => {
      const l = i.lastDataRef;
      l && x(i, l, "navigate_next");
    }, i.handlers.onKey = (l) => {
      const p = l.target;
      if (p && (p.tagName === "INPUT" || p.tagName === "TEXTAREA" || p.isContentEditable))
        return;
      if (!e.contains(document.activeElement) && document.activeElement !== e) {
        const d = i.host;
        if (!("contains" in d ? d.contains(document.activeElement) : !1)) return;
      }
      if (i.lastDataRef) {
        if (l.key === "Enter")
          l.preventDefault(), i.handlers.onSave();
        else if (l.key === " " || l.code === "Space")
          l.preventDefault(), i.audio.paused ? i.audio.play().catch(() => {
          }) : i.audio.pause();
        else if (l.key === "j" || l.key === "ArrowDown")
          l.preventDefault(), i.handlers.onNext();
        else if (l.key === "k" || l.key === "ArrowUp")
          l.preventDefault(), i.handlers.onPrev();
        else if (l.key === "i")
          l.preventDefault(), i.handlers.onIgnore();
        else if (l.key === "?") {
          const d = u(e, ".tx-sid-help");
          d.hidden = !d.hidden, d.textContent = "Shortcuts (workspace focused): j/↓ next · k/↑ prev · Space play/pause · Enter save · i ignore · ? help";
        }
      }
    };
  })(), u(e, ".tx-sid-save").addEventListener(
    "click",
    () => i.handlers.onSave()
  ), u(e, ".tx-sid-ignore").addEventListener(
    "click",
    () => i.handlers.onIgnore()
  ), u(e, ".tx-sid-prev").addEventListener(
    "click",
    () => i.handlers.onPrev()
  ), u(e, ".tx-sid-next").addEventListener(
    "click",
    () => i.handlers.onNext()
  );
  const o = u(e, ".tx-sid-name-input"), a = u(e, ".tx-sid-name-pick");
  o.addEventListener("input", () => {
    const l = i.lastDataRef;
    l && P(e, l);
  }), a.addEventListener("change", () => {
    var m;
    const l = i.lastDataRef;
    if (!l) return;
    const p = l.name_suggestions, d = (((m = p == null ? void 0 : p.by_speaker) == null ? void 0 : m[l.active_speaker_id]) || []).find((C) => C.display_name === a.value);
    d && ($(o, a, d), P(e, l), F(e, l));
  }), ("addEventListener" in t ? t : e).addEventListener(
    "keydown",
    (l) => i.handlers.onKey(l)
  );
  const f = e.querySelector(".tx-sid-root") || e;
  return f.hasAttribute("tabindex") || f.setAttribute("tabindex", "0"), i;
}
const oe = (t) => {
  var o, a;
  const { parentElement: e, data: n } = t, s = e, i = ((o = s.querySelector) == null ? void 0 : o.call(s, ".tx-sid-root")) || ((a = s.querySelector) == null ? void 0 : a.call(s, ".tx-sid-root")) || s;
  let r = b.get(s);
  return r ? (r.setTriggerValue = t.setTriggerValue, r.setStateValue = t.setStateValue) : (r = se(s, i, t), b.set(s, r)), ie(i, n, r), () => {
    const c = b.get(s);
    c && (k(c), c.pendingPlay = null, A(c), c.audio.removeAttribute("src"), c.audio.load(), b.delete(s));
  };
}, le = {
  instances: b,
  ensureBlobUrl: D,
  revokeAllBlobs: A,
  PROTOCOL_VERSION: E,
  FRONTEND_BUILD_ID: S,
  parseLinkToken: O,
  rankLinkRows: j,
  expectedSpeakerForCommand(t, e) {
    return t.active_speaker_id;
  },
  applyNamePick: $,
  partitionRosterForDisplay: L,
  findPlayableSample: U,
  playSampleBlob: T
};
export {
  le as __test,
  $ as applyNamePick,
  oe as default,
  L as partitionRosterForDisplay,
  j as rankLinkRows
};
