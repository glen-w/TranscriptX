const g = /* @__PURE__ */ new WeakMap(), k = "tx-workspaces-0.2.0", v = "1", S = 8e6, M = 4, U = 200, N = 3e3, B = 2;
function C() {
  return typeof crypto < "u" && "randomUUID" in crypto ? crypto.randomUUID().replace(/-/g, "") : `a${Date.now().toString(16)}${Math.random().toString(16).slice(2)}`;
}
function c(t, e) {
  const i = t.querySelector(e);
  if (!i) throw new Error(`Missing element: ${e}`);
  return i;
}
function E(t) {
  for (const e of t.blobUrls.values())
    URL.revokeObjectURL(e);
  t.blobUrls.clear(), t.blobBytes = 0;
}
function R(t, e, i, s) {
  const n = t.blobUrls.get(e);
  if (n) return n;
  try {
    const o = atob(i);
    if (t.blobBytes + o.length > s)
      return null;
    const l = new Uint8Array(o.length);
    for (let r = 0; r < o.length; r++) l[r] = o.charCodeAt(r);
    const a = URL.createObjectURL(new Blob([l], { type: "audio/mpeg" }));
    return t.blobUrls.set(e, a), t.blobBytes += o.length, a;
  } catch {
    return null;
  }
}
function _(t, e, i, s = {}, n = {}) {
  const o = !!n.mutating;
  if (o && t.mutating) return;
  if (e.protocol_version !== v || e.frontend_build_id !== k) {
    t.setTriggerValue("command", {
      protocol_version: v,
      frontend_build_id: k,
      action_id: C(),
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
  o && (t.mutating = !0);
  const l = {
    protocol_version: v,
    frontend_build_id: k,
    action_id: C(),
    action_seq: ++t.actionSeq,
    transcript_id: e.transcript_id,
    transcript_revision: e.transcript_revision,
    expected_speaker_id: e.active_speaker_id,
    expected_mapping_revision: e.mapping_revision,
    audio_fingerprint: e.audio_fingerprint ?? null,
    action: i,
    payload: s
  };
  t.setTriggerValue("command", l), t.setStateValue("ack_seq", l.action_seq);
}
function x(t) {
  for (const e of t.retryTimers) window.clearTimeout(e);
  t.retryTimers = [], t.activeMissRetries = 0;
}
function h(t, e) {
  x(t), t.pendingPlay = null;
  const i = e.querySelector(".tx-sid-clip-status");
  i && (i.textContent = "");
}
function V(t) {
  return Math.min(N, U * 2 ** t);
}
function I(t, e, i, s) {
  if (!i.clip_b64) return !1;
  const n = R(t, i.clip_id, i.clip_b64, s);
  return n ? (t.audio.src !== n && (t.audio.src = n), t.audio.play().catch(() => {
  }), c(e, ".tx-sid-clip-status").textContent = "", !0) : !1;
}
function P(t, e, i) {
  const s = t.pendingPlay;
  if (!s) return;
  if (s.attempt >= M) {
    c(e, ".tx-sid-clip-status").textContent = "Clip still preparing — click ▶ again.", t.pendingPlay = null;
    return;
  }
  if (t.activeMissRetries >= B) return;
  const n = V(s.attempt);
  s.attempt += 1, t.activeMissRetries += 1;
  const o = window.setTimeout(() => {
    t.activeMissRetries = Math.max(0, t.activeMissRetries - 1);
    const l = t.pendingPlay, a = t.lastDataRef;
    !l || !a || l.clipId !== s.clipId || (c(e, ".tx-sid-clip-status").textContent = "Preparing clip…", _(t, a, "refresh_clips", {
      clip_id: l.clipId,
      start: l.start,
      end: l.end
    }), P(t, e));
  }, n);
  t.retryTimers.push(o);
}
function O(t, e, i, s) {
  var l;
  const n = ((l = i.budgets) == null ? void 0 : l.max_blob_bytes) ?? S;
  if (I(t, e, s, n)) {
    h(t, e);
    return;
  }
  const o = s.clip_status || "";
  if (o === "unavailable" || o === "too_large") {
    x(t), t.pendingPlay = null, c(e, ".tx-sid-clip-status").textContent = o === "too_large" ? "Clip too large to load." : "Clip unavailable.";
    return;
  }
  x(t), t.pendingPlay = {
    clipId: s.clip_id,
    start: s.start,
    end: s.end,
    attempt: 0
  }, c(e, ".tx-sid-clip-status").textContent = "Preparing clip…", _(t, i, "enqueue_clip", {
    clip_id: s.clip_id,
    start: s.start,
    end: s.end
  }), P(t, e);
}
function T(t, e) {
  const i = t.samples || [], s = i.find((n) => n.clip_id === e.clipId);
  return s || i.find(
    (n) => Math.abs(n.start - e.start) < 1e-3 && Math.abs(n.end - e.end) < 1e-3
  );
}
function j(t, e, i) {
  var l;
  const s = t.pendingPlay;
  if (!s) return;
  const n = T(i, s);
  if (!n) return;
  const o = ((l = i.budgets) == null ? void 0 : l.max_blob_bytes) ?? S;
  if (I(t, e, n, o)) {
    h(t, e);
    return;
  }
  (n.clip_status === "unavailable" || n.clip_status === "too_large") && (x(t), t.pendingPlay = null, c(e, ".tx-sid-clip-status").textContent = n.clip_status === "too_large" ? "Clip too large to load." : "Clip unavailable.");
}
function w(t, e, i) {
  const s = c(t, ".tx-sid-speakers");
  s.replaceChildren();
  const n = i.optimisticSpeakerId ?? e.active_speaker_id;
  for (const o of e.speakers || []) {
    const l = document.createElement("button");
    l.type = "button", l.className = "tx-sid-speaker-btn", l.textContent = o.label, o.id === n && l.setAttribute("aria-current", "true"), l.addEventListener("click", () => {
      i.optimisticSpeakerId = o.id, _(i, e, "navigate_jump", {
        target_speaker_id: o.id
      }), w(t, e, i);
    }), s.appendChild(l);
  }
}
function $(t, e, i) {
  const s = c(t, ".tx-sid-samples");
  s.replaceChildren();
  for (const n of e.samples || []) {
    const o = document.createElement("li");
    o.className = "tx-sid-sample";
    const l = document.createElement("button");
    l.type = "button", l.className = "tx-sid-sample-play", l.textContent = "▶", l.setAttribute("aria-label", "Play sample"), l.addEventListener("click", () => {
      O(i, t, e, n);
    });
    const a = document.createElement("div");
    a.textContent = n.text || "", o.append(l, a), s.appendChild(o);
  }
}
function F(t, e, i) {
  const s = c(t, ".tx-sid-paging");
  s.replaceChildren();
  const n = e.paging;
  if (!n || n.shown >= n.total) {
    s.hidden = !0;
    return;
  }
  s.hidden = !1;
  const o = n.total - n.shown, l = Math.min(n.page_size, o), a = document.createElement("button");
  a.type = "button", a.className = "tx-sid-load-more", a.textContent = `Show ${l} more lines`, a.addEventListener("click", () => {
    _(i, e, "load_more_samples", { n: l });
  }), s.appendChild(a);
}
function b(t) {
  return t.mode === "existing" && t.profile_id ? `existing:${t.profile_id}` : t.mode || "none";
}
function L(t) {
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
function A(t) {
  return t.trim().replace(/\s+/g, " ").toLocaleLowerCase();
}
function K(t, e) {
  const i = [t.display_name || "", ...t.aliases || []].map(A);
  return i.some((s) => s === e) ? 0 : i.some((s) => s.startsWith(e)) ? 1 : 3;
}
function D(t, e) {
  const i = A(e), s = t.filter((r) => r.mode === "existing"), n = t.filter((r) => r.mode !== "existing"), o = s.map((r, u) => ({
    row: r,
    index: u,
    score: i ? K(r, i) : 3
  })), l = o.filter((r) => i && r.score < 3).sort((r, u) => r.score - u.score || r.index - u.index).map((r) => r.row), a = o.filter((r) => !i || r.score >= 3).sort((r, u) => r.index - u.index).map((r) => r.row);
  return [...l, ...n, ...a];
}
function q(t, e) {
  var y;
  const i = c(t, ".tx-sid-link-select"), s = c(t, ".tx-sid-link-chip"), n = !!(e.link_profile_allowed ?? ((y = e.capabilities) == null ? void 0 : y.profile_link)), o = t.querySelector(".tx-sid-name-input"), l = (o == null ? void 0 : o.value) || e.draft_name || "", a = D(e.link_targets || [], l), r = i.value;
  i.replaceChildren();
  for (const d of a) {
    const m = document.createElement("option");
    m.value = b(d), m.textContent = d.label, d.is_default && (m.selected = !0), i.appendChild(m);
  }
  if (!a.length) {
    const d = document.createElement("option");
    d.value = "none", d.textContent = "Name only — this transcript", i.appendChild(d);
  }
  const u = Array.from(i.options).map((d) => d.value);
  if (r && u.includes(r))
    i.value = r;
  else {
    const d = a.find((m) => m.is_default);
    d && (i.value = b(d));
  }
  i.disabled = !n && u.every((d) => d === "none" || d === "");
  const f = a.find((d) => b(d) === i.value), p = [];
  f != null && f.detail && p.push(f.detail), f != null && f.duplicate_name_warning && p.push("A profile with this name already exists."), e.recipe_hint && p.push(e.recipe_hint), s.textContent = p.join(" ");
}
function W(t, e, i) {
  var l, a;
  (i.lastTranscriptId !== e.transcript_id || i.lastSpeakerId !== e.active_speaker_id) && (h(i, t), i.lastTranscriptId = e.transcript_id, i.lastSpeakerId = e.active_speaker_id), c(t, ".tx-sid-title").textContent = `Speaker ${e.active_speaker_id}`;
  const s = c(t, ".tx-sid-status");
  s.textContent = ((l = e.ui) == null ? void 0 : l.status) || "", e.ack && e.ack.action_seq >= i.lastAckSeq && (i.lastAckSeq = e.ack.action_seq, e.ack.action_seq >= i.actionSeq - 0, (e.ack.status === "ok" || e.ack.status === "partial" || e.ack.status === "error" || e.ack.status === "rejected_stale" || e.ack.status === "rejected_protocol") && (i.mutating = !1, i.optimisticSpeakerId = null), e.ack.status === "rejected_protocol" && (s.textContent = e.ack.message || "Protocol mismatch — reload or use classic UI."));
  const n = c(t, ".tx-sid-name-input");
  document.activeElement !== n && (n.value = e.draft_name || ""), q(t, e);
  const o = !!((a = e.ui) != null && a.disabled || i.mutating);
  for (const r of [".tx-sid-save", ".tx-sid-ignore", ".tx-sid-prev", ".tx-sid-next"])
    c(t, r).disabled = o;
  w(t, e, i), $(t, e, i), F(t, e, i), i.lastDataRef = e, j(i, t, e);
}
function X(t, e, i) {
  const n = {
    wired: !0,
    audio: c(e, ".tx-sid-audio"),
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
      const r = n.lastDataRef;
      if (!r) return;
      const u = c(e, ".tx-sid-name-input").value.trim(), f = c(e, ".tx-sid-link-select").value, p = L(f);
      _(
        n,
        r,
        "save_name",
        {
          display_name: u,
          link_profile: p.link_profile,
          link_mode: p.link_mode,
          profile_id: p.profile_id
        },
        { mutating: !0 }
      );
    }, n.handlers.onIgnore = () => {
      const r = n.lastDataRef;
      r && _(n, r, "ignore_toggle", {}, { mutating: !0 });
    }, n.handlers.onPrev = () => {
      const r = n.lastDataRef;
      r && _(n, r, "navigate_prev");
    }, n.handlers.onNext = () => {
      const r = n.lastDataRef;
      r && _(n, r, "navigate_next");
    }, n.handlers.onKey = (r) => {
      const u = r.target;
      if (u && (u.tagName === "INPUT" || u.tagName === "TEXTAREA" || u.isContentEditable))
        return;
      if (!e.contains(document.activeElement) && document.activeElement !== e) {
        const p = n.host;
        if (!("contains" in p ? p.contains(document.activeElement) : !1)) return;
      }
      if (n.lastDataRef) {
        if (r.key === "Enter")
          r.preventDefault(), n.handlers.onSave();
        else if (r.key === " " || r.code === "Space")
          r.preventDefault(), n.audio.paused ? n.audio.play().catch(() => {
          }) : n.audio.pause();
        else if (r.key === "j" || r.key === "ArrowDown")
          r.preventDefault(), n.handlers.onNext();
        else if (r.key === "k" || r.key === "ArrowUp")
          r.preventDefault(), n.handlers.onPrev();
        else if (r.key === "i")
          r.preventDefault(), n.handlers.onIgnore();
        else if (r.key === "?") {
          const p = c(e, ".tx-sid-help");
          p.hidden = !p.hidden, p.textContent = "Shortcuts (workspace focused): j/↓ next · k/↑ prev · Space play/pause · Enter save · i ignore · ? help";
        }
      }
    };
  })(), c(e, ".tx-sid-save").addEventListener(
    "click",
    () => n.handlers.onSave()
  ), c(e, ".tx-sid-ignore").addEventListener(
    "click",
    () => n.handlers.onIgnore()
  ), c(e, ".tx-sid-prev").addEventListener(
    "click",
    () => n.handlers.onPrev()
  ), c(e, ".tx-sid-next").addEventListener(
    "click",
    () => n.handlers.onNext()
  ), c(e, ".tx-sid-name-input").addEventListener("input", () => {
    const r = n.lastDataRef;
    r && q(e, r);
  }), ("addEventListener" in t ? t : e).addEventListener(
    "keydown",
    (r) => n.handlers.onKey(r)
  );
  const a = e.querySelector(".tx-sid-root") || e;
  return a.hasAttribute("tabindex") || a.setAttribute("tabindex", "0"), n;
}
const Y = (t) => {
  var l, a;
  const { parentElement: e, data: i } = t, s = e, n = ((l = s.querySelector) == null ? void 0 : l.call(s, ".tx-sid-root")) || ((a = s.querySelector) == null ? void 0 : a.call(s, ".tx-sid-root")) || s;
  let o = g.get(s);
  return o ? (o.setTriggerValue = t.setTriggerValue, o.setStateValue = t.setStateValue) : (o = X(s, n, t), g.set(s, o)), W(n, i, o), () => {
    const r = g.get(s);
    r && (x(r), r.pendingPlay = null, E(r), r.audio.removeAttribute("src"), r.audio.load(), g.delete(s));
  };
}, H = {
  instances: g,
  ensureBlobUrl: R,
  revokeAllBlobs: E,
  PROTOCOL_VERSION: v,
  FRONTEND_BUILD_ID: k,
  parseLinkToken: L,
  rankLinkRows: D,
  expectedSpeakerForCommand(t, e) {
    return t.active_speaker_id;
  },
  findPlayableSample: T
};
export {
  H as __test,
  Y as default,
  D as rankLinkRows
};
