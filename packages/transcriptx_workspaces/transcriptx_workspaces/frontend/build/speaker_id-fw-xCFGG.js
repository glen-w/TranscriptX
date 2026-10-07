import { F as y, P as b } from "./constants-dt4zPgAn.js";
const k = /* @__PURE__ */ new WeakMap(), P = 8e6, V = 4, O = 200, j = 3e3, $ = 2;
function R() {
  return typeof crypto < "u" && "randomUUID" in crypto ? crypto.randomUUID().replace(/-/g, "") : `a${Date.now().toString(16)}${Math.random().toString(16).slice(2)}`;
}
function u(t, e) {
  const i = t.querySelector(e);
  if (!i) throw new Error(`Missing element: ${e}`);
  return i;
}
function I(t) {
  for (const e of t.blobUrls.values())
    URL.revokeObjectURL(e);
  t.blobUrls.clear(), t.blobBytes = 0;
}
function T(t, e, i, s) {
  const n = t.blobUrls.get(e);
  if (n) return n;
  try {
    const r = atob(i);
    if (t.blobBytes + r.length > s)
      return null;
    const o = new Uint8Array(r.length);
    for (let a = 0; a < r.length; a++) o[a] = r.charCodeAt(a);
    const c = URL.createObjectURL(new Blob([o], { type: "audio/mpeg" }));
    return t.blobUrls.set(e, c), t.blobBytes += r.length, c;
  } catch {
    return null;
  }
}
function x(t, e, i, s = {}, n = {}) {
  const r = !!n.mutating;
  if (r && t.mutating) return;
  if (e.protocol_version !== b || e.frontend_build_id !== y) {
    t.setTriggerValue("command", {
      protocol_version: b,
      frontend_build_id: y,
      action_id: R(),
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
    protocol_version: b,
    frontend_build_id: y,
    action_id: R(),
    action_seq: ++t.actionSeq,
    transcript_id: e.transcript_id,
    transcript_revision: e.transcript_revision,
    expected_speaker_id: e.active_speaker_id,
    expected_mapping_revision: e.mapping_revision,
    audio_fingerprint: e.audio_fingerprint ?? null,
    action: i,
    payload: s
  };
  t.setTriggerValue("command", o), t.setStateValue("ack_seq", o.action_seq);
}
function v(t) {
  for (const e of t.retryTimers) window.clearTimeout(e);
  t.retryTimers = [], t.activeMissRetries = 0;
}
function E(t, e) {
  v(t), t.pendingPlay = null;
  const i = e.querySelector(".tx-sid-clip-status");
  i && (i.textContent = "");
}
function F(t) {
  return Math.min(j, O * 2 ** t);
}
function q(t, e, i, s) {
  if (!i.clip_b64) return !1;
  const n = T(t, i.clip_id, i.clip_b64, s);
  return n ? (t.audio.src !== n && (t.audio.src = n), t.audio.play().catch(() => {
  }), u(e, ".tx-sid-clip-status").textContent = "", !0) : !1;
}
function L(t, e, i) {
  const s = t.pendingPlay;
  if (!s) return;
  if (s.attempt >= V) {
    u(e, ".tx-sid-clip-status").textContent = "Clip still preparing — click ▶ again.", t.pendingPlay = null;
    return;
  }
  if (t.activeMissRetries >= $) return;
  const n = F(s.attempt);
  s.attempt += 1, t.activeMissRetries += 1;
  const r = window.setTimeout(() => {
    t.activeMissRetries = Math.max(0, t.activeMissRetries - 1);
    const o = t.pendingPlay, c = t.lastDataRef;
    !o || !c || o.clipId !== s.clipId || (u(e, ".tx-sid-clip-status").textContent = "Preparing clip…", x(t, c, "refresh_clips", {
      clip_id: o.clipId,
      start: o.start,
      end: o.end
    }), L(t, e));
  }, n);
  t.retryTimers.push(r);
}
function K(t, e, i, s) {
  var o;
  const n = ((o = i.budgets) == null ? void 0 : o.max_blob_bytes) ?? P;
  if (q(t, e, s, n)) {
    E(t, e);
    return;
  }
  const r = s.clip_status || "";
  if (r === "unavailable" || r === "too_large") {
    v(t), t.pendingPlay = null, u(e, ".tx-sid-clip-status").textContent = r === "too_large" ? "Clip too large to load." : "Clip unavailable.";
    return;
  }
  v(t), t.pendingPlay = {
    clipId: s.clip_id,
    start: s.start,
    end: s.end,
    attempt: 0
  }, u(e, ".tx-sid-clip-status").textContent = "Preparing clip…", x(t, i, "enqueue_clip", {
    clip_id: s.clip_id,
    start: s.start,
    end: s.end
  }), L(t, e);
}
function w(t, e) {
  const i = t.samples || [], s = i.find((n) => n.clip_id === e.clipId);
  return s || i.find(
    (n) => Math.abs(n.start - e.start) < 1e-3 && Math.abs(n.end - e.end) < 1e-3
  );
}
function W(t, e, i) {
  var o;
  const s = t.pendingPlay;
  if (!s) return;
  const n = w(i, s);
  if (!n) return;
  const r = ((o = i.budgets) == null ? void 0 : o.max_blob_bytes) ?? P;
  if (q(t, e, n, r)) {
    E(t, e);
    return;
  }
  (n.clip_status === "unavailable" || n.clip_status === "too_large") && (v(t), t.pendingPlay = null, u(e, ".tx-sid-clip-status").textContent = n.clip_status === "too_large" ? "Clip too large to load." : "Clip unavailable.");
}
function A(t, e, i) {
  const s = u(t, ".tx-sid-speakers");
  s.replaceChildren();
  const n = i.optimisticSpeakerId ?? e.active_speaker_id;
  for (const r of e.speakers || []) {
    const o = document.createElement("button");
    o.type = "button", o.className = "tx-sid-speaker-btn", o.textContent = r.label, r.id === n && o.setAttribute("aria-current", "true"), o.addEventListener("click", () => {
      i.optimisticSpeakerId = r.id, x(i, e, "navigate_jump", {
        target_speaker_id: r.id
      }), A(t, e, i);
    }), s.appendChild(o);
  }
}
function X(t, e, i) {
  const s = u(t, ".tx-sid-samples");
  s.replaceChildren();
  for (const n of e.samples || []) {
    const r = document.createElement("li");
    r.className = "tx-sid-sample";
    const o = document.createElement("button");
    o.type = "button", o.className = "tx-sid-sample-play", o.textContent = "▶", o.setAttribute("aria-label", "Play sample"), o.addEventListener("click", () => {
      K(i, t, e, n);
    });
    const c = document.createElement("div");
    c.textContent = n.text || "", r.append(o, c), s.appendChild(r);
  }
}
function Y(t, e, i) {
  const s = u(t, ".tx-sid-paging");
  s.replaceChildren();
  const n = e.paging;
  if (!n || n.shown >= n.total) {
    s.hidden = !0;
    return;
  }
  s.hidden = !1;
  const r = n.total - n.shown, o = Math.min(n.page_size, r), c = document.createElement("button");
  c.type = "button", c.className = "tx-sid-load-more", c.textContent = `Show ${o} more lines`, c.addEventListener("click", () => {
    x(i, e, "load_more_samples", { n: o });
  }), s.appendChild(c);
}
function C(t) {
  return t.mode === "existing" && t.profile_id ? `existing:${t.profile_id}` : t.mode || "none";
}
function D(t) {
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
function M(t) {
  return t.trim().replace(/\s+/g, " ").toLocaleLowerCase();
}
function H(t, e) {
  const i = [t.display_name || "", ...t.aliases || []].map(M);
  return i.some((s) => s === e) ? 0 : i.some((s) => s.startsWith(e)) ? 1 : 3;
}
function N(t, e) {
  const i = M(e), s = t.filter((a) => a.mode === "existing"), n = t.filter((a) => a.mode !== "existing"), r = s.map((a, m) => ({
    row: a,
    index: m,
    score: i ? H(a, i) : 3
  })), o = r.filter((a) => i && a.score < 3).sort((a, m) => a.score - m.score || a.index - m.index).map((a) => a.row), c = r.filter((a) => !i || a.score >= 3).sort((a, m) => a.index - m.index).map((a) => a.row);
  return [...o, ...n, ...c];
}
function U(t, e, i) {
  const s = i.display_name || "";
  if (t.value = s, s) {
    if (!Array.from(e.options).some((r) => r.value === s)) {
      const r = document.createElement("option");
      r.value = s, r.textContent = i.label || s, e.appendChild(r);
    }
    e.value = s;
  }
  t.dispatchEvent(new Event("input", { bubbles: !0 }));
}
function B(t, e) {
  var d;
  const i = t.querySelector(".tx-sid-name-pick"), s = t.querySelector(".tx-sid-name-datalist"), n = t.querySelector(".tx-sid-name-hint"), r = t.querySelector(".tx-sid-roster"), o = t.querySelector(".tx-sid-roster-list");
  if (!i || !s || !n || !r || !o) return;
  const c = e.name_suggestions, a = ((d = c == null ? void 0 : c.by_speaker) == null ? void 0 : d[e.active_speaker_id]) || [];
  i.replaceChildren();
  const m = document.createElement("option");
  m.value = "", m.textContent = a.length ? "Suggested names…" : "No suggestions yet", i.appendChild(m), s.replaceChildren();
  for (const p of a) {
    const g = document.createElement("option");
    g.value = p.display_name, g.textContent = p.label || p.display_name, i.appendChild(g);
    const h = document.createElement("option");
    h.value = p.display_name, s.appendChild(h);
  }
  const l = i.value, f = a.find((p) => p.display_name === l);
  f != null && f.quote ? n.textContent = f.quote : c != null && c.status_message && !a.length ? n.textContent = c.status_message : n.textContent = "";
  const _ = (c == null ? void 0 : c.roster) || [];
  if (o.replaceChildren(), _.length) {
    r.hidden = !1;
    for (const p of _) {
      const g = document.createElement("li"), h = p.mention_count ? ` (${p.mention_count})` : "";
      g.textContent = `${p.display_name}${h}`, o.appendChild(g);
    }
  } else
    r.hidden = !0;
}
function S(t, e) {
  var _;
  const i = u(t, ".tx-sid-link-select"), s = u(t, ".tx-sid-link-chip"), n = !!(e.link_profile_allowed ?? ((_ = e.capabilities) == null ? void 0 : _.profile_link)), r = t.querySelector(".tx-sid-name-input"), o = (r == null ? void 0 : r.value) || e.draft_name || "", c = N(e.link_targets || [], o), a = i.value;
  i.replaceChildren();
  for (const d of c) {
    const p = document.createElement("option");
    p.value = C(d), p.textContent = d.label, d.is_default && (p.selected = !0), i.appendChild(p);
  }
  if (!c.length) {
    const d = document.createElement("option");
    d.value = "none", d.textContent = "Name only — this transcript", i.appendChild(d);
  }
  const m = Array.from(i.options).map((d) => d.value);
  if (a && m.includes(a))
    i.value = a;
  else {
    const d = c.find((p) => p.is_default);
    d && (i.value = C(d));
  }
  i.disabled = !n && m.every((d) => d === "none" || d === "");
  const l = c.find((d) => C(d) === i.value), f = [];
  l != null && l.detail && f.push(l.detail), l != null && l.duplicate_name_warning && f.push("A profile with this name already exists."), e.recipe_hint && f.push(e.recipe_hint), s.textContent = f.join(" ");
}
function z(t, e, i) {
  var o, c;
  (i.lastTranscriptId !== e.transcript_id || i.lastSpeakerId !== e.active_speaker_id) && (E(i, t), i.lastTranscriptId = e.transcript_id, i.lastSpeakerId = e.active_speaker_id), u(t, ".tx-sid-title").textContent = `Speaker ${e.active_speaker_id}`;
  const s = u(t, ".tx-sid-status");
  s.textContent = ((o = e.ui) == null ? void 0 : o.status) || "", e.ack && e.ack.action_seq >= i.lastAckSeq && (i.lastAckSeq = e.ack.action_seq, e.ack.action_seq >= i.actionSeq - 0, (e.ack.status === "ok" || e.ack.status === "partial" || e.ack.status === "error" || e.ack.status === "rejected_stale" || e.ack.status === "rejected_protocol") && (i.mutating = !1, i.optimisticSpeakerId = null), e.ack.status === "rejected_protocol" && (s.textContent = e.ack.message || "Protocol mismatch — reload or use classic UI."));
  const n = u(t, ".tx-sid-name-input");
  document.activeElement !== n && (n.value = e.draft_name || ""), S(t, e), B(t, e);
  const r = !!((c = e.ui) != null && c.disabled || i.mutating);
  for (const a of [".tx-sid-save", ".tx-sid-ignore", ".tx-sid-prev", ".tx-sid-next"])
    u(t, a).disabled = r;
  A(t, e, i), X(t, e, i), Y(t, e, i), i.lastDataRef = e, W(i, t, e);
}
function G(t, e, i) {
  const n = {
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
    setTriggerValue: i.setTriggerValue,
    setStateValue: i.setStateValue,
    host: t
  };
  (() => {
    n.handlers.onSave = () => {
      const l = n.lastDataRef;
      if (!l) return;
      const f = u(e, ".tx-sid-name-input").value.trim(), _ = u(e, ".tx-sid-link-select").value, d = D(_);
      x(
        n,
        l,
        "save_name",
        {
          display_name: f,
          link_profile: d.link_profile,
          link_mode: d.link_mode,
          profile_id: d.profile_id
        },
        { mutating: !0 }
      );
    }, n.handlers.onIgnore = () => {
      const l = n.lastDataRef;
      l && x(n, l, "ignore_toggle", {}, { mutating: !0 });
    }, n.handlers.onPrev = () => {
      const l = n.lastDataRef;
      l && x(n, l, "navigate_prev");
    }, n.handlers.onNext = () => {
      const l = n.lastDataRef;
      l && x(n, l, "navigate_next");
    }, n.handlers.onKey = (l) => {
      const f = l.target;
      if (f && (f.tagName === "INPUT" || f.tagName === "TEXTAREA" || f.isContentEditable))
        return;
      if (!e.contains(document.activeElement) && document.activeElement !== e) {
        const d = n.host;
        if (!("contains" in d ? d.contains(document.activeElement) : !1)) return;
      }
      if (n.lastDataRef) {
        if (l.key === "Enter")
          l.preventDefault(), n.handlers.onSave();
        else if (l.key === " " || l.code === "Space")
          l.preventDefault(), n.audio.paused ? n.audio.play().catch(() => {
          }) : n.audio.pause();
        else if (l.key === "j" || l.key === "ArrowDown")
          l.preventDefault(), n.handlers.onNext();
        else if (l.key === "k" || l.key === "ArrowUp")
          l.preventDefault(), n.handlers.onPrev();
        else if (l.key === "i")
          l.preventDefault(), n.handlers.onIgnore();
        else if (l.key === "?") {
          const d = u(e, ".tx-sid-help");
          d.hidden = !d.hidden, d.textContent = "Shortcuts (workspace focused): j/↓ next · k/↑ prev · Space play/pause · Enter save · i ignore · ? help";
        }
      }
    };
  })(), u(e, ".tx-sid-save").addEventListener(
    "click",
    () => n.handlers.onSave()
  ), u(e, ".tx-sid-ignore").addEventListener(
    "click",
    () => n.handlers.onIgnore()
  ), u(e, ".tx-sid-prev").addEventListener(
    "click",
    () => n.handlers.onPrev()
  ), u(e, ".tx-sid-next").addEventListener(
    "click",
    () => n.handlers.onNext()
  );
  const o = u(e, ".tx-sid-name-input"), c = u(e, ".tx-sid-name-pick");
  o.addEventListener("input", () => {
    const l = n.lastDataRef;
    l && S(e, l);
  }), c.addEventListener("change", () => {
    var p;
    const l = n.lastDataRef;
    if (!l) return;
    const f = l.name_suggestions, d = (((p = f == null ? void 0 : f.by_speaker) == null ? void 0 : p[l.active_speaker_id]) || []).find((g) => g.display_name === c.value);
    d && (U(o, c, d), S(e, l), B(e, l));
  }), ("addEventListener" in t ? t : e).addEventListener(
    "keydown",
    (l) => n.handlers.onKey(l)
  );
  const m = e.querySelector(".tx-sid-root") || e;
  return m.hasAttribute("tabindex") || m.setAttribute("tabindex", "0"), n;
}
const Q = (t) => {
  var o, c;
  const { parentElement: e, data: i } = t, s = e, n = ((o = s.querySelector) == null ? void 0 : o.call(s, ".tx-sid-root")) || ((c = s.querySelector) == null ? void 0 : c.call(s, ".tx-sid-root")) || s;
  let r = k.get(s);
  return r ? (r.setTriggerValue = t.setTriggerValue, r.setStateValue = t.setStateValue) : (r = G(s, n, t), k.set(s, r)), z(n, i, r), () => {
    const a = k.get(s);
    a && (v(a), a.pendingPlay = null, I(a), a.audio.removeAttribute("src"), a.audio.load(), k.delete(s));
  };
}, Z = {
  instances: k,
  ensureBlobUrl: T,
  revokeAllBlobs: I,
  PROTOCOL_VERSION: b,
  FRONTEND_BUILD_ID: y,
  parseLinkToken: D,
  rankLinkRows: N,
  expectedSpeakerForCommand(t, e) {
    return t.active_speaker_id;
  },
  applyNamePick: U,
  findPlayableSample: w
};
export {
  Z as __test,
  U as applyNamePick,
  Q as default,
  N as rankLinkRows
};
