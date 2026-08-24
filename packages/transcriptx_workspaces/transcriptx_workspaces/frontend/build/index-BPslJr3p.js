const f = /* @__PURE__ */ new WeakMap(), g = "tx-workspaces-0.1.0", b = "1", v = 8e6, R = 4, P = 200, T = 3e3, w = 2;
function x() {
  return typeof crypto < "u" && "randomUUID" in crypto ? crypto.randomUUID().replace(/-/g, "") : `a${Date.now().toString(16)}${Math.random().toString(16).slice(2)}`;
}
function c(t, e) {
  const i = t.querySelector(e);
  if (!i) throw new Error(`Missing element: ${e}`);
  return i;
}
function y(t) {
  for (const e of t.blobUrls.values())
    URL.revokeObjectURL(e);
  t.blobUrls.clear(), t.blobBytes = 0;
}
function h(t, e, i, r) {
  const n = t.blobUrls.get(e);
  if (n) return n;
  try {
    const o = atob(i);
    if (t.blobBytes + o.length > r)
      return null;
    const l = new Uint8Array(o.length);
    for (let s = 0; s < o.length; s++) l[s] = o.charCodeAt(s);
    const a = URL.createObjectURL(new Blob([l], { type: "audio/mpeg" }));
    return t.blobUrls.set(e, a), t.blobBytes += o.length, a;
  } catch {
    return null;
  }
}
function u(t, e, i, r = {}, n = {}) {
  const o = !!n.mutating;
  if (o && t.mutating) return;
  if (e.protocol_version !== b || e.frontend_build_id !== g) {
    t.setTriggerValue("command", {
      protocol_version: b,
      frontend_build_id: g,
      action_id: x(),
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
    protocol_version: b,
    frontend_build_id: g,
    action_id: x(),
    action_seq: ++t.actionSeq,
    transcript_id: e.transcript_id,
    transcript_revision: e.transcript_revision,
    expected_speaker_id: e.active_speaker_id,
    expected_mapping_revision: e.mapping_revision,
    audio_fingerprint: e.audio_fingerprint ?? null,
    action: i,
    payload: r
  };
  t.setTriggerValue("command", l), t.setStateValue("ack_seq", l.action_seq);
}
function _(t) {
  for (const e of t.retryTimers) window.clearTimeout(e);
  t.retryTimers = [], t.activeMissRetries = 0;
}
function k(t, e) {
  _(t), t.pendingPlay = null;
  const i = e.querySelector(".tx-sid-clip-status");
  i && (i.textContent = "");
}
function D(t) {
  return Math.min(T, P * 2 ** t);
}
function S(t, e, i, r) {
  if (!i.clip_b64) return !1;
  const n = h(t, i.clip_id, i.clip_b64, r);
  return n ? (t.audio.src !== n && (t.audio.src = n), t.audio.play().catch(() => {
  }), c(e, ".tx-sid-clip-status").textContent = "", !0) : !1;
}
function C(t, e, i) {
  const r = t.pendingPlay;
  if (!r) return;
  if (r.attempt >= R) {
    c(e, ".tx-sid-clip-status").textContent = "Clip still preparing — click ▶ again.", t.pendingPlay = null;
    return;
  }
  if (t.activeMissRetries >= w) return;
  const n = D(r.attempt);
  r.attempt += 1, t.activeMissRetries += 1;
  const o = window.setTimeout(() => {
    t.activeMissRetries = Math.max(0, t.activeMissRetries - 1);
    const l = t.pendingPlay, a = t.lastDataRef;
    !l || !a || l.clipId !== r.clipId || (c(e, ".tx-sid-clip-status").textContent = "Preparing clip…", u(t, a, "refresh_clips", {
      clip_id: l.clipId,
      start: l.start,
      end: l.end
    }), C(t, e));
  }, n);
  t.retryTimers.push(o);
}
function q(t, e, i, r) {
  var l;
  const n = ((l = i.budgets) == null ? void 0 : l.max_blob_bytes) ?? v;
  if (S(t, e, r, n)) {
    k(t, e);
    return;
  }
  const o = r.clip_status || "";
  if (o === "unavailable" || o === "too_large") {
    _(t), t.pendingPlay = null, c(e, ".tx-sid-clip-status").textContent = o === "too_large" ? "Clip too large to load." : "Clip unavailable.";
    return;
  }
  _(t), t.pendingPlay = {
    clipId: r.clip_id,
    start: r.start,
    end: r.end,
    attempt: 0
  }, c(e, ".tx-sid-clip-status").textContent = "Preparing clip…", u(t, i, "enqueue_clip", {
    clip_id: r.clip_id,
    start: r.start,
    end: r.end
  }), C(t, e);
}
function E(t, e) {
  const i = t.samples || [], r = i.find((n) => n.clip_id === e.clipId);
  return r || i.find(
    (n) => Math.abs(n.start - e.start) < 1e-3 && Math.abs(n.end - e.end) < 1e-3
  );
}
function A(t, e, i) {
  var l;
  const r = t.pendingPlay;
  if (!r) return;
  const n = E(i, r);
  if (!n) return;
  const o = ((l = i.budgets) == null ? void 0 : l.max_blob_bytes) ?? v;
  if (S(t, e, n, o)) {
    k(t, e);
    return;
  }
  (n.clip_status === "unavailable" || n.clip_status === "too_large") && (_(t), t.pendingPlay = null, c(e, ".tx-sid-clip-status").textContent = n.clip_status === "too_large" ? "Clip too large to load." : "Clip unavailable.");
}
function I(t, e, i) {
  const r = c(t, ".tx-sid-speakers");
  r.replaceChildren();
  const n = i.optimisticSpeakerId ?? e.active_speaker_id;
  for (const o of e.speakers || []) {
    const l = document.createElement("button");
    l.type = "button", l.className = "tx-sid-speaker-btn", l.textContent = o.label, o.id === n && l.setAttribute("aria-current", "true"), l.addEventListener("click", () => {
      i.optimisticSpeakerId = o.id, u(i, e, "navigate_jump", {
        target_speaker_id: o.id
      }), I(t, e, i);
    }), r.appendChild(l);
  }
}
function M(t, e, i) {
  const r = c(t, ".tx-sid-samples");
  r.replaceChildren();
  for (const n of e.samples || []) {
    const o = document.createElement("li");
    o.className = "tx-sid-sample";
    const l = document.createElement("button");
    l.type = "button", l.className = "tx-sid-sample-play", l.textContent = "▶", l.setAttribute("aria-label", "Play sample"), l.addEventListener("click", () => {
      q(i, t, e, n);
    });
    const a = document.createElement("div");
    a.textContent = n.text || "", o.append(l, a), r.appendChild(o);
  }
}
function L(t, e, i) {
  const r = c(t, ".tx-sid-paging");
  r.replaceChildren();
  const n = e.paging;
  if (!n || n.shown >= n.total) {
    r.hidden = !0;
    return;
  }
  r.hidden = !1;
  const o = n.total - n.shown, l = Math.min(n.page_size, o), a = document.createElement("button");
  a.type = "button", a.className = "tx-sid-load-more", a.textContent = `Show ${l} more lines`, a.addEventListener("click", () => {
    u(i, e, "load_more_samples", { n: l });
  }), r.appendChild(a);
}
function U(t, e, i) {
  var a, s, d;
  (i.lastTranscriptId !== e.transcript_id || i.lastSpeakerId !== e.active_speaker_id) && (k(i, t), i.lastTranscriptId = e.transcript_id, i.lastSpeakerId = e.active_speaker_id), c(t, ".tx-sid-title").textContent = `Speaker ${e.active_speaker_id}`;
  const r = c(t, ".tx-sid-status");
  r.textContent = ((a = e.ui) == null ? void 0 : a.status) || "", e.ack && e.ack.action_seq >= i.lastAckSeq && (i.lastAckSeq = e.ack.action_seq, e.ack.action_seq >= i.actionSeq - 0, (e.ack.status === "ok" || e.ack.status === "partial" || e.ack.status === "error" || e.ack.status === "rejected_stale" || e.ack.status === "rejected_protocol") && (i.mutating = !1, i.optimisticSpeakerId = null), e.ack.status === "rejected_protocol" && (r.textContent = e.ack.message || "Protocol mismatch — reload or use classic UI."));
  const n = c(t, ".tx-sid-name-input");
  document.activeElement !== n && (n.value = e.draft_name || "");
  const o = c(t, ".tx-sid-link-profile");
  o.disabled = !(e.link_profile_allowed ?? ((s = e.capabilities) == null ? void 0 : s.profile_link));
  const l = !!((d = e.ui) != null && d.disabled || i.mutating);
  for (const m of [".tx-sid-save", ".tx-sid-ignore", ".tx-sid-prev", ".tx-sid-next"])
    c(t, m).disabled = l;
  I(t, e, i), M(t, e, i), L(t, e, i), i.lastDataRef = e, A(i, t, e);
}
function N(t, e, i) {
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
      const s = n.lastDataRef;
      if (!s) return;
      const d = c(e, ".tx-sid-name-input").value.trim(), m = c(e, ".tx-sid-link-profile").checked;
      u(
        n,
        s,
        "save_name",
        { display_name: d, link_profile: m },
        { mutating: !0 }
      );
    }, n.handlers.onIgnore = () => {
      const s = n.lastDataRef;
      s && u(n, s, "ignore_toggle", {}, { mutating: !0 });
    }, n.handlers.onPrev = () => {
      const s = n.lastDataRef;
      s && u(n, s, "navigate_prev");
    }, n.handlers.onNext = () => {
      const s = n.lastDataRef;
      s && u(n, s, "navigate_next");
    }, n.handlers.onKey = (s) => {
      const d = s.target;
      if (d && (d.tagName === "INPUT" || d.tagName === "TEXTAREA" || d.isContentEditable))
        return;
      if (!e.contains(document.activeElement) && document.activeElement !== e) {
        const p = n.host;
        if (!("contains" in p ? p.contains(document.activeElement) : !1)) return;
      }
      if (n.lastDataRef) {
        if (s.key === "Enter")
          s.preventDefault(), n.handlers.onSave();
        else if (s.key === " " || s.code === "Space")
          s.preventDefault(), n.audio.paused ? n.audio.play().catch(() => {
          }) : n.audio.pause();
        else if (s.key === "j" || s.key === "ArrowDown")
          s.preventDefault(), n.handlers.onNext();
        else if (s.key === "k" || s.key === "ArrowUp")
          s.preventDefault(), n.handlers.onPrev();
        else if (s.key === "i")
          s.preventDefault(), n.handlers.onIgnore();
        else if (s.key === "?") {
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
  ), ("addEventListener" in t ? t : e).addEventListener(
    "keydown",
    (s) => n.handlers.onKey(s)
  );
  const a = e.querySelector(".tx-sid-root") || e;
  return a.hasAttribute("tabindex") || a.setAttribute("tabindex", "0"), n;
}
const V = (t) => {
  var l, a;
  const { parentElement: e, data: i } = t, r = e, n = ((l = r.querySelector) == null ? void 0 : l.call(r, ".tx-sid-root")) || ((a = r.querySelector) == null ? void 0 : a.call(r, ".tx-sid-root")) || r;
  let o = f.get(r);
  return o ? (o.setTriggerValue = t.setTriggerValue, o.setStateValue = t.setStateValue) : (o = N(r, n, t), f.set(r, o)), U(n, i, o), () => {
    const s = f.get(r);
    s && (_(s), s.pendingPlay = null, y(s), s.audio.removeAttribute("src"), s.audio.load(), f.delete(r));
  };
}, O = {
  instances: f,
  ensureBlobUrl: h,
  revokeAllBlobs: y,
  PROTOCOL_VERSION: b,
  FRONTEND_BUILD_ID: g,
  /** Mirrors fireCommand expected_speaker_id selection (authoritative only). */
  expectedSpeakerForCommand(t, e) {
    return t.active_speaker_id;
  },
  findPlayableSample: E
};
export {
  O as __test,
  V as default
};
