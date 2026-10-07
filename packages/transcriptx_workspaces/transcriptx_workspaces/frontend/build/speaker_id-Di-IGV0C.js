import { F as b, P as C } from "./constants-dt4zPgAn.js";
const v = /* @__PURE__ */ new WeakMap(), I = 8e6, V = 4, O = 200, j = 3e3, $ = 2;
function P() {
  return typeof crypto < "u" && "randomUUID" in crypto ? crypto.randomUUID().replace(/-/g, "") : `a${Date.now().toString(16)}${Math.random().toString(16).slice(2)}`;
}
function u(n, e) {
  const t = n.querySelector(e);
  if (!t) throw new Error(`Missing element: ${e}`);
  return t;
}
function T(n) {
  for (const e of n.blobUrls.values())
    URL.revokeObjectURL(e);
  n.blobUrls.clear(), n.blobBytes = 0;
}
function q(n, e, t, s) {
  const i = n.blobUrls.get(e);
  if (i) return i;
  try {
    const r = atob(t);
    if (n.blobBytes + r.length > s)
      return null;
    const l = new Uint8Array(r.length);
    for (let c = 0; c < r.length; c++) l[c] = r.charCodeAt(c);
    const a = URL.createObjectURL(new Blob([l], { type: "audio/mpeg" }));
    return n.blobUrls.set(e, a), n.blobBytes += r.length, a;
  } catch {
    return null;
  }
}
function y(n, e, t, s = {}, i = {}) {
  const r = !!i.mutating;
  if (r && n.mutating) return;
  if (e.protocol_version !== C || e.frontend_build_id !== b) {
    n.setTriggerValue("command", {
      protocol_version: C,
      frontend_build_id: b,
      action_id: P(),
      action_seq: ++n.actionSeq,
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
  r && (n.mutating = !0);
  const l = {
    protocol_version: C,
    frontend_build_id: b,
    action_id: P(),
    action_seq: ++n.actionSeq,
    transcript_id: e.transcript_id,
    transcript_revision: e.transcript_revision,
    expected_speaker_id: e.active_speaker_id,
    expected_mapping_revision: e.mapping_revision,
    audio_fingerprint: e.audio_fingerprint ?? null,
    action: t,
    payload: s
  };
  n.setTriggerValue("command", l), n.setStateValue("ack_seq", l.action_seq);
}
function x(n) {
  for (const e of n.retryTimers) window.clearTimeout(e);
  n.retryTimers = [], n.activeMissRetries = 0;
}
function F(n, e) {
  x(n), n.pendingPlay = null;
  const t = e.querySelector(".tx-sid-clip-status");
  t && (t.textContent = "");
}
function K(n) {
  return Math.min(j, O * 2 ** n);
}
function k(n, e) {
  u(n, ".tx-sid-clip-status").textContent = e;
}
function R(n, e, t, s, i = {}) {
  if (!t.clip_b64) return !1;
  const r = q(n, t.clip_id, t.clip_b64, s);
  if (!r) return !1;
  const l = i.autoplay !== !1;
  if (n.audio.src !== r)
    n.audio.src = r;
  else if (l)
    try {
      n.audio.currentTime = 0;
    } catch {
    }
  return l ? (k(e, ""), n.audio.play().then(() => {
    k(e, "");
  }).catch((a) => {
    const c = a && typeof a == "object" && "name" in a ? String(a.name) : "";
    if (c !== "AbortError") {
      if (c === "NotAllowedError") {
        k(e, "Ready — click ▶ to play");
        return;
      }
      k(e, "Playback failed — click ▶ again.");
    }
  }), !0) : (k(e, "Ready — click ▶ to play"), !0);
}
function w(n, e, t) {
  const s = n.pendingPlay;
  if (!s) return;
  if (s.attempt >= V) {
    u(e, ".tx-sid-clip-status").textContent = "Clip still preparing — click ▶ again.", n.pendingPlay = null;
    return;
  }
  if (n.activeMissRetries >= $) return;
  const i = K(s.attempt);
  s.attempt += 1, n.activeMissRetries += 1;
  const r = window.setTimeout(() => {
    n.activeMissRetries = Math.max(0, n.activeMissRetries - 1);
    const l = n.pendingPlay, a = n.lastDataRef;
    !l || !a || l.clipId !== s.clipId || (u(e, ".tx-sid-clip-status").textContent = "Preparing clip…", y(n, a, "refresh_clips", {
      clip_id: l.clipId,
      start: l.start,
      end: l.end
    }), w(n, e));
  }, i);
  n.retryTimers.push(r);
}
function W(n, e, t, s) {
  var l;
  const i = ((l = t.budgets) == null ? void 0 : l.max_blob_bytes) ?? I;
  if (R(n, e, s, i, { autoplay: !0 })) {
    x(n), n.pendingPlay = null;
    return;
  }
  const r = s.clip_status || "";
  if (r === "unavailable" || r === "too_large") {
    x(n), n.pendingPlay = null, k(
      e,
      r === "too_large" ? "Clip too large to load." : "Clip unavailable."
    );
    return;
  }
  x(n), n.pendingPlay = {
    clipId: s.clip_id,
    start: s.start,
    end: s.end,
    attempt: 0
  }, k(e, "Preparing clip…"), y(n, t, "enqueue_clip", {
    clip_id: s.clip_id,
    start: s.start,
    end: s.end
  }), w(n, e);
}
function L(n, e) {
  const t = n.samples || [], s = t.find((i) => i.clip_id === e.clipId);
  return s || t.find(
    (i) => Math.abs(i.start - e.start) < 1e-3 && Math.abs(i.end - e.end) < 1e-3
  );
}
function X(n, e, t) {
  var l;
  const s = n.pendingPlay;
  if (!s) return;
  const i = L(t, s);
  if (!i) return;
  const r = ((l = t.budgets) == null ? void 0 : l.max_blob_bytes) ?? I;
  if (R(n, e, i, r, { autoplay: !0 })) {
    x(n), n.pendingPlay = null;
    return;
  }
  (i.clip_status === "unavailable" || i.clip_status === "too_large") && (x(n), n.pendingPlay = null, k(
    e,
    i.clip_status === "too_large" ? "Clip too large to load." : "Clip unavailable."
  ));
}
function A(n, e, t) {
  const s = u(n, ".tx-sid-speakers");
  s.replaceChildren();
  const i = t.optimisticSpeakerId ?? e.active_speaker_id;
  for (const r of e.speakers || []) {
    const l = document.createElement("button");
    l.type = "button", l.className = "tx-sid-speaker-btn", l.textContent = r.label, r.id === i && l.setAttribute("aria-current", "true"), l.addEventListener("click", () => {
      t.optimisticSpeakerId = r.id, y(t, e, "navigate_jump", {
        target_speaker_id: r.id
      }), A(n, e, t);
    }), s.appendChild(l);
  }
}
function Y(n, e, t) {
  const s = u(n, ".tx-sid-samples");
  s.replaceChildren();
  for (const i of e.samples || []) {
    const r = document.createElement("li");
    r.className = "tx-sid-sample";
    const l = document.createElement("button");
    l.type = "button", l.className = "tx-sid-sample-play", l.textContent = "▶", l.setAttribute("aria-label", "Play sample"), l.addEventListener("click", () => {
      W(t, n, e, i);
    });
    const a = document.createElement("div");
    a.textContent = i.text || "", r.append(l, a), s.appendChild(r);
  }
}
function H(n, e, t) {
  const s = u(n, ".tx-sid-paging");
  s.replaceChildren();
  const i = e.paging;
  if (!i || i.shown >= i.total) {
    s.hidden = !0;
    return;
  }
  s.hidden = !1;
  const r = i.total - i.shown, l = Math.min(i.page_size, r), a = document.createElement("button");
  a.type = "button", a.className = "tx-sid-load-more", a.textContent = `Show ${l} more lines`, a.addEventListener("click", () => {
    y(t, e, "load_more_samples", { n: l });
  }), s.appendChild(a);
}
function S(n) {
  return n.mode === "existing" && n.profile_id ? `existing:${n.profile_id}` : n.mode || "none";
}
function D(n) {
  if (n.startsWith("existing:")) {
    const e = n.slice(9).trim() || null;
    return {
      link_mode: e ? "existing" : "none",
      profile_id: e,
      link_profile: !!e
    };
  }
  return n === "create" ? { link_mode: "create", profile_id: null, link_profile: !0 } : { link_mode: "none", profile_id: null, link_profile: !1 };
}
function N(n) {
  return n.trim().replace(/\s+/g, " ").toLocaleLowerCase();
}
function z(n, e) {
  const t = [n.display_name || "", ...n.aliases || []].map(N);
  return t.some((s) => s === e) ? 0 : t.some((s) => s.startsWith(e)) ? 1 : 3;
}
function M(n, e) {
  const t = N(e), s = n.filter((c) => c.mode === "existing"), i = n.filter((c) => c.mode !== "existing"), r = s.map((c, m) => ({
    row: c,
    index: m,
    score: t ? z(c, t) : 3
  })), l = r.filter((c) => t && c.score < 3).sort((c, m) => c.score - m.score || c.index - m.index).map((c) => c.row), a = r.filter((c) => !t || c.score >= 3).sort((c, m) => c.index - m.index).map((c) => c.row);
  return [...l, ...i, ...a];
}
function U(n, e, t) {
  const s = t.display_name || "";
  if (n.value = s, s) {
    if (!Array.from(e.options).some((r) => r.value === s)) {
      const r = document.createElement("option");
      r.value = s, r.textContent = t.label || s, e.appendChild(r);
    }
    e.value = s;
  }
  n.dispatchEvent(new Event("input", { bubbles: !0 }));
}
function B(n, e) {
  var d;
  const t = n.querySelector(".tx-sid-name-pick"), s = n.querySelector(".tx-sid-name-datalist"), i = n.querySelector(".tx-sid-name-hint"), r = n.querySelector(".tx-sid-roster"), l = n.querySelector(".tx-sid-roster-list");
  if (!t || !s || !i || !r || !l) return;
  const a = e.name_suggestions, c = ((d = a == null ? void 0 : a.by_speaker) == null ? void 0 : d[e.active_speaker_id]) || [];
  t.replaceChildren();
  const m = document.createElement("option");
  m.value = "", m.textContent = c.length ? "Suggested names…" : "No suggestions yet", t.appendChild(m), s.replaceChildren();
  for (const p of c) {
    const g = document.createElement("option");
    g.value = p.display_name, g.textContent = p.label || p.display_name, t.appendChild(g);
    const h = document.createElement("option");
    h.value = p.display_name, s.appendChild(h);
  }
  const o = t.value, f = c.find((p) => p.display_name === o);
  f != null && f.quote ? i.textContent = f.quote : a != null && a.status_message && !c.length ? i.textContent = a.status_message : i.textContent = "";
  const _ = (a == null ? void 0 : a.roster) || [];
  if (l.replaceChildren(), _.length) {
    r.hidden = !1;
    for (const p of _) {
      const g = document.createElement("li"), h = p.mention_count ? ` (${p.mention_count})` : "";
      g.textContent = `${p.display_name}${h}`, l.appendChild(g);
    }
  } else
    r.hidden = !0;
}
function E(n, e) {
  var _;
  const t = u(n, ".tx-sid-link-select"), s = u(n, ".tx-sid-link-chip"), i = !!(e.link_profile_allowed ?? ((_ = e.capabilities) == null ? void 0 : _.profile_link)), r = n.querySelector(".tx-sid-name-input"), l = (r == null ? void 0 : r.value) || e.draft_name || "", a = M(e.link_targets || [], l), c = t.value;
  t.replaceChildren();
  for (const d of a) {
    const p = document.createElement("option");
    p.value = S(d), p.textContent = d.label, d.is_default && (p.selected = !0), t.appendChild(p);
  }
  if (!a.length) {
    const d = document.createElement("option");
    d.value = "none", d.textContent = "Name only — this transcript", t.appendChild(d);
  }
  const m = Array.from(t.options).map((d) => d.value);
  if (c && m.includes(c))
    t.value = c;
  else {
    const d = a.find((p) => p.is_default);
    d && (t.value = S(d));
  }
  t.disabled = !i && m.every((d) => d === "none" || d === "");
  const o = a.find((d) => S(d) === t.value), f = [];
  o != null && o.detail && f.push(o.detail), o != null && o.duplicate_name_warning && f.push("A profile with this name already exists."), e.recipe_hint && f.push(e.recipe_hint), s.textContent = f.join(" ");
}
function G(n, e, t) {
  var l, a;
  (t.lastTranscriptId !== e.transcript_id || t.lastSpeakerId !== e.active_speaker_id) && (F(t, n), t.lastTranscriptId = e.transcript_id, t.lastSpeakerId = e.active_speaker_id), u(n, ".tx-sid-title").textContent = `Speaker ${e.active_speaker_id}`;
  const s = u(n, ".tx-sid-status");
  s.textContent = ((l = e.ui) == null ? void 0 : l.status) || "", e.ack && e.ack.action_seq >= t.lastAckSeq && (t.lastAckSeq = e.ack.action_seq, e.ack.action_seq >= t.actionSeq - 0, (e.ack.status === "ok" || e.ack.status === "partial" || e.ack.status === "error" || e.ack.status === "rejected_stale" || e.ack.status === "rejected_protocol") && (t.mutating = !1, t.optimisticSpeakerId = null), e.ack.status === "rejected_protocol" && (s.textContent = e.ack.message || "Protocol mismatch — reload or use classic UI."));
  const i = u(n, ".tx-sid-name-input");
  document.activeElement !== i && (i.value = e.draft_name || ""), E(n, e), B(n, e);
  const r = !!((a = e.ui) != null && a.disabled || t.mutating);
  for (const c of [".tx-sid-save", ".tx-sid-ignore", ".tx-sid-prev", ".tx-sid-next"])
    u(n, c).disabled = r;
  A(n, e, t), Y(n, e, t), H(n, e, t), t.lastDataRef = e, X(t, n, e);
}
function J(n, e, t) {
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
    setTriggerValue: t.setTriggerValue,
    setStateValue: t.setStateValue,
    host: n
  };
  (() => {
    i.handlers.onSave = () => {
      const o = i.lastDataRef;
      if (!o) return;
      const f = u(e, ".tx-sid-name-input").value.trim(), _ = u(e, ".tx-sid-link-select").value, d = D(_);
      y(
        i,
        o,
        "save_name",
        {
          display_name: f,
          link_profile: d.link_profile,
          link_mode: d.link_mode,
          profile_id: d.profile_id
        },
        { mutating: !0 }
      );
    }, i.handlers.onIgnore = () => {
      const o = i.lastDataRef;
      o && y(i, o, "ignore_toggle", {}, { mutating: !0 });
    }, i.handlers.onPrev = () => {
      const o = i.lastDataRef;
      o && y(i, o, "navigate_prev");
    }, i.handlers.onNext = () => {
      const o = i.lastDataRef;
      o && y(i, o, "navigate_next");
    }, i.handlers.onKey = (o) => {
      const f = o.target;
      if (f && (f.tagName === "INPUT" || f.tagName === "TEXTAREA" || f.isContentEditable))
        return;
      if (!e.contains(document.activeElement) && document.activeElement !== e) {
        const d = i.host;
        if (!("contains" in d ? d.contains(document.activeElement) : !1)) return;
      }
      if (i.lastDataRef) {
        if (o.key === "Enter")
          o.preventDefault(), i.handlers.onSave();
        else if (o.key === " " || o.code === "Space")
          o.preventDefault(), i.audio.paused ? i.audio.play().catch(() => {
          }) : i.audio.pause();
        else if (o.key === "j" || o.key === "ArrowDown")
          o.preventDefault(), i.handlers.onNext();
        else if (o.key === "k" || o.key === "ArrowUp")
          o.preventDefault(), i.handlers.onPrev();
        else if (o.key === "i")
          o.preventDefault(), i.handlers.onIgnore();
        else if (o.key === "?") {
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
  const l = u(e, ".tx-sid-name-input"), a = u(e, ".tx-sid-name-pick");
  l.addEventListener("input", () => {
    const o = i.lastDataRef;
    o && E(e, o);
  }), a.addEventListener("change", () => {
    var p;
    const o = i.lastDataRef;
    if (!o) return;
    const f = o.name_suggestions, d = (((p = f == null ? void 0 : f.by_speaker) == null ? void 0 : p[o.active_speaker_id]) || []).find((g) => g.display_name === a.value);
    d && (U(l, a, d), E(e, o), B(e, o));
  }), ("addEventListener" in n ? n : e).addEventListener(
    "keydown",
    (o) => i.handlers.onKey(o)
  );
  const m = e.querySelector(".tx-sid-root") || e;
  return m.hasAttribute("tabindex") || m.setAttribute("tabindex", "0"), i;
}
const Z = (n) => {
  var l, a;
  const { parentElement: e, data: t } = n, s = e, i = ((l = s.querySelector) == null ? void 0 : l.call(s, ".tx-sid-root")) || ((a = s.querySelector) == null ? void 0 : a.call(s, ".tx-sid-root")) || s;
  let r = v.get(s);
  return r ? (r.setTriggerValue = n.setTriggerValue, r.setStateValue = n.setStateValue) : (r = J(s, i, n), v.set(s, r)), G(i, t, r), () => {
    const c = v.get(s);
    c && (x(c), c.pendingPlay = null, T(c), c.audio.removeAttribute("src"), c.audio.load(), v.delete(s));
  };
}, ee = {
  instances: v,
  ensureBlobUrl: q,
  revokeAllBlobs: T,
  PROTOCOL_VERSION: C,
  FRONTEND_BUILD_ID: b,
  parseLinkToken: D,
  rankLinkRows: M,
  expectedSpeakerForCommand(n, e) {
    return n.active_speaker_id;
  },
  applyNamePick: U,
  findPlayableSample: L,
  playSampleBlob: R
};
export {
  ee as __test,
  U as applyNamePick,
  Z as default,
  M as rankLinkRows
};
