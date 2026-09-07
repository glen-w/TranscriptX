const m = /* @__PURE__ */ new WeakMap(), k = "tx-workspaces-0.2.0", x = "1", h = 8e6, w = 4, A = 200, D = 3e3, L = 2;
function y() {
  return typeof crypto < "u" && "randomUUID" in crypto ? crypto.randomUUID().replace(/-/g, "") : `a${Date.now().toString(16)}${Math.random().toString(16).slice(2)}`;
}
function d(n, e) {
  const i = n.querySelector(e);
  if (!i) throw new Error(`Missing element: ${e}`);
  return i;
}
function C(n) {
  for (const e of n.blobUrls.values())
    URL.revokeObjectURL(e);
  n.blobUrls.clear(), n.blobBytes = 0;
}
function S(n, e, i, r) {
  const t = n.blobUrls.get(e);
  if (t) return t;
  try {
    const o = atob(i);
    if (n.blobBytes + o.length > r)
      return null;
    const s = new Uint8Array(o.length);
    for (let l = 0; l < o.length; l++) s[l] = o.charCodeAt(l);
    const c = URL.createObjectURL(new Blob([s], { type: "audio/mpeg" }));
    return n.blobUrls.set(e, c), n.blobBytes += o.length, c;
  } catch {
    return null;
  }
}
function p(n, e, i, r = {}, t = {}) {
  const o = !!t.mutating;
  if (o && n.mutating) return;
  if (e.protocol_version !== x || e.frontend_build_id !== k) {
    n.setTriggerValue("command", {
      protocol_version: x,
      frontend_build_id: k,
      action_id: y(),
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
  o && (n.mutating = !0);
  const s = {
    protocol_version: x,
    frontend_build_id: k,
    action_id: y(),
    action_seq: ++n.actionSeq,
    transcript_id: e.transcript_id,
    transcript_revision: e.transcript_revision,
    expected_speaker_id: e.active_speaker_id,
    expected_mapping_revision: e.mapping_revision,
    audio_fingerprint: e.audio_fingerprint ?? null,
    action: i,
    payload: r
  };
  n.setTriggerValue("command", s), n.setStateValue("ack_seq", s.action_seq);
}
function g(n) {
  for (const e of n.retryTimers) window.clearTimeout(e);
  n.retryTimers = [], n.activeMissRetries = 0;
}
function b(n, e) {
  g(n), n.pendingPlay = null;
  const i = e.querySelector(".tx-sid-clip-status");
  i && (i.textContent = "");
}
function q(n) {
  return Math.min(D, A * 2 ** n);
}
function E(n, e, i, r) {
  if (!i.clip_b64) return !1;
  const t = S(n, i.clip_id, i.clip_b64, r);
  return t ? (n.audio.src !== t && (n.audio.src = t), n.audio.play().catch(() => {
  }), d(e, ".tx-sid-clip-status").textContent = "", !0) : !1;
}
function I(n, e, i) {
  const r = n.pendingPlay;
  if (!r) return;
  if (r.attempt >= w) {
    d(e, ".tx-sid-clip-status").textContent = "Clip still preparing — click ▶ again.", n.pendingPlay = null;
    return;
  }
  if (n.activeMissRetries >= L) return;
  const t = q(r.attempt);
  r.attempt += 1, n.activeMissRetries += 1;
  const o = window.setTimeout(() => {
    n.activeMissRetries = Math.max(0, n.activeMissRetries - 1);
    const s = n.pendingPlay, c = n.lastDataRef;
    !s || !c || s.clipId !== r.clipId || (d(e, ".tx-sid-clip-status").textContent = "Preparing clip…", p(n, c, "refresh_clips", {
      clip_id: s.clipId,
      start: s.start,
      end: s.end
    }), I(n, e));
  }, t);
  n.retryTimers.push(o);
}
function M(n, e, i, r) {
  var s;
  const t = ((s = i.budgets) == null ? void 0 : s.max_blob_bytes) ?? h;
  if (E(n, e, r, t)) {
    b(n, e);
    return;
  }
  const o = r.clip_status || "";
  if (o === "unavailable" || o === "too_large") {
    g(n), n.pendingPlay = null, d(e, ".tx-sid-clip-status").textContent = o === "too_large" ? "Clip too large to load." : "Clip unavailable.";
    return;
  }
  g(n), n.pendingPlay = {
    clipId: r.clip_id,
    start: r.start,
    end: r.end,
    attempt: 0
  }, d(e, ".tx-sid-clip-status").textContent = "Preparing clip…", p(n, i, "enqueue_clip", {
    clip_id: r.clip_id,
    start: r.start,
    end: r.end
  }), I(n, e);
}
function R(n, e) {
  const i = n.samples || [], r = i.find((t) => t.clip_id === e.clipId);
  return r || i.find(
    (t) => Math.abs(t.start - e.start) < 1e-3 && Math.abs(t.end - e.end) < 1e-3
  );
}
function U(n, e, i) {
  var s;
  const r = n.pendingPlay;
  if (!r) return;
  const t = R(i, r);
  if (!t) return;
  const o = ((s = i.budgets) == null ? void 0 : s.max_blob_bytes) ?? h;
  if (E(n, e, t, o)) {
    b(n, e);
    return;
  }
  (t.clip_status === "unavailable" || t.clip_status === "too_large") && (g(n), n.pendingPlay = null, d(e, ".tx-sid-clip-status").textContent = t.clip_status === "too_large" ? "Clip too large to load." : "Clip unavailable.");
}
function P(n, e, i) {
  const r = d(n, ".tx-sid-speakers");
  r.replaceChildren();
  const t = i.optimisticSpeakerId ?? e.active_speaker_id;
  for (const o of e.speakers || []) {
    const s = document.createElement("button");
    s.type = "button", s.className = "tx-sid-speaker-btn", s.textContent = o.label, o.id === t && s.setAttribute("aria-current", "true"), s.addEventListener("click", () => {
      i.optimisticSpeakerId = o.id, p(i, e, "navigate_jump", {
        target_speaker_id: o.id
      }), P(n, e, i);
    }), r.appendChild(s);
  }
}
function B(n, e, i) {
  const r = d(n, ".tx-sid-samples");
  r.replaceChildren();
  for (const t of e.samples || []) {
    const o = document.createElement("li");
    o.className = "tx-sid-sample";
    const s = document.createElement("button");
    s.type = "button", s.className = "tx-sid-sample-play", s.textContent = "▶", s.setAttribute("aria-label", "Play sample"), s.addEventListener("click", () => {
      M(i, n, e, t);
    });
    const c = document.createElement("div");
    c.textContent = t.text || "", o.append(s, c), r.appendChild(o);
  }
}
function N(n, e, i) {
  const r = d(n, ".tx-sid-paging");
  r.replaceChildren();
  const t = e.paging;
  if (!t || t.shown >= t.total) {
    r.hidden = !0;
    return;
  }
  r.hidden = !1;
  const o = t.total - t.shown, s = Math.min(t.page_size, o), c = document.createElement("button");
  c.type = "button", c.className = "tx-sid-load-more", c.textContent = `Show ${s} more lines`, c.addEventListener("click", () => {
    p(i, e, "load_more_samples", { n: s });
  }), r.appendChild(c);
}
function v(n) {
  return n.mode === "existing" && n.profile_id ? `existing:${n.profile_id}` : n.mode || "none";
}
function T(n) {
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
function V(n, e) {
  var _;
  const i = d(n, ".tx-sid-link-select"), r = d(n, ".tx-sid-link-chip"), t = !!(e.link_profile_allowed ?? ((_ = e.capabilities) == null ? void 0 : _.profile_link)), o = e.link_targets || [], s = i.value;
  i.replaceChildren();
  for (const a of o) {
    const f = document.createElement("option");
    f.value = v(a), f.textContent = a.label, a.is_default && (f.selected = !0), i.appendChild(f);
  }
  if (!o.length) {
    const a = document.createElement("option");
    a.value = "none", a.textContent = "Name only — this transcript", i.appendChild(a);
  }
  const c = Array.from(i.options).map((a) => a.value);
  if (s && c.includes(s))
    i.value = s;
  else {
    const a = o.find((f) => f.is_default);
    a && (i.value = v(a));
  }
  i.disabled = !t && c.every((a) => a === "none" || a === "");
  const l = o.find((a) => v(a) === i.value), u = [];
  l != null && l.detail && u.push(l.detail), l != null && l.duplicate_name_warning && u.push("A profile with this name already exists."), e.recipe_hint && u.push(e.recipe_hint), r.textContent = u.join(" ");
}
function O(n, e, i) {
  var s, c;
  (i.lastTranscriptId !== e.transcript_id || i.lastSpeakerId !== e.active_speaker_id) && (b(i, n), i.lastTranscriptId = e.transcript_id, i.lastSpeakerId = e.active_speaker_id), d(n, ".tx-sid-title").textContent = `Speaker ${e.active_speaker_id}`;
  const r = d(n, ".tx-sid-status");
  r.textContent = ((s = e.ui) == null ? void 0 : s.status) || "", e.ack && e.ack.action_seq >= i.lastAckSeq && (i.lastAckSeq = e.ack.action_seq, e.ack.action_seq >= i.actionSeq - 0, (e.ack.status === "ok" || e.ack.status === "partial" || e.ack.status === "error" || e.ack.status === "rejected_stale" || e.ack.status === "rejected_protocol") && (i.mutating = !1, i.optimisticSpeakerId = null), e.ack.status === "rejected_protocol" && (r.textContent = e.ack.message || "Protocol mismatch — reload or use classic UI."));
  const t = d(n, ".tx-sid-name-input");
  document.activeElement !== t && (t.value = e.draft_name || ""), V(n, e);
  const o = !!((c = e.ui) != null && c.disabled || i.mutating);
  for (const l of [".tx-sid-save", ".tx-sid-ignore", ".tx-sid-prev", ".tx-sid-next"])
    d(n, l).disabled = o;
  P(n, e, i), B(n, e, i), N(n, e, i), i.lastDataRef = e, U(i, n, e);
}
function j(n, e, i) {
  const t = {
    wired: !0,
    audio: d(e, ".tx-sid-audio"),
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
    host: n
  };
  (() => {
    t.handlers.onSave = () => {
      const l = t.lastDataRef;
      if (!l) return;
      const u = d(e, ".tx-sid-name-input").value.trim(), _ = d(e, ".tx-sid-link-select").value, a = T(_);
      p(
        t,
        l,
        "save_name",
        {
          display_name: u,
          link_profile: a.link_profile,
          link_mode: a.link_mode,
          profile_id: a.profile_id
        },
        { mutating: !0 }
      );
    }, t.handlers.onIgnore = () => {
      const l = t.lastDataRef;
      l && p(t, l, "ignore_toggle", {}, { mutating: !0 });
    }, t.handlers.onPrev = () => {
      const l = t.lastDataRef;
      l && p(t, l, "navigate_prev");
    }, t.handlers.onNext = () => {
      const l = t.lastDataRef;
      l && p(t, l, "navigate_next");
    }, t.handlers.onKey = (l) => {
      const u = l.target;
      if (u && (u.tagName === "INPUT" || u.tagName === "TEXTAREA" || u.isContentEditable))
        return;
      if (!e.contains(document.activeElement) && document.activeElement !== e) {
        const a = t.host;
        if (!("contains" in a ? a.contains(document.activeElement) : !1)) return;
      }
      if (t.lastDataRef) {
        if (l.key === "Enter")
          l.preventDefault(), t.handlers.onSave();
        else if (l.key === " " || l.code === "Space")
          l.preventDefault(), t.audio.paused ? t.audio.play().catch(() => {
          }) : t.audio.pause();
        else if (l.key === "j" || l.key === "ArrowDown")
          l.preventDefault(), t.handlers.onNext();
        else if (l.key === "k" || l.key === "ArrowUp")
          l.preventDefault(), t.handlers.onPrev();
        else if (l.key === "i")
          l.preventDefault(), t.handlers.onIgnore();
        else if (l.key === "?") {
          const a = d(e, ".tx-sid-help");
          a.hidden = !a.hidden, a.textContent = "Shortcuts (workspace focused): j/↓ next · k/↑ prev · Space play/pause · Enter save · i ignore · ? help";
        }
      }
    };
  })(), d(e, ".tx-sid-save").addEventListener(
    "click",
    () => t.handlers.onSave()
  ), d(e, ".tx-sid-ignore").addEventListener(
    "click",
    () => t.handlers.onIgnore()
  ), d(e, ".tx-sid-prev").addEventListener(
    "click",
    () => t.handlers.onPrev()
  ), d(e, ".tx-sid-next").addEventListener(
    "click",
    () => t.handlers.onNext()
  ), ("addEventListener" in n ? n : e).addEventListener(
    "keydown",
    (l) => t.handlers.onKey(l)
  );
  const c = e.querySelector(".tx-sid-root") || e;
  return c.hasAttribute("tabindex") || c.setAttribute("tabindex", "0"), t;
}
const $ = (n) => {
  var s, c;
  const { parentElement: e, data: i } = n, r = e, t = ((s = r.querySelector) == null ? void 0 : s.call(r, ".tx-sid-root")) || ((c = r.querySelector) == null ? void 0 : c.call(r, ".tx-sid-root")) || r;
  let o = m.get(r);
  return o ? (o.setTriggerValue = n.setTriggerValue, o.setStateValue = n.setStateValue) : (o = j(r, t, n), m.set(r, o)), O(t, i, o), () => {
    const l = m.get(r);
    l && (g(l), l.pendingPlay = null, C(l), l.audio.removeAttribute("src"), l.audio.load(), m.delete(r));
  };
}, F = {
  instances: m,
  ensureBlobUrl: S,
  revokeAllBlobs: C,
  PROTOCOL_VERSION: x,
  FRONTEND_BUILD_ID: k,
  parseLinkToken: T,
  expectedSpeakerForCommand(n, e) {
    return n.active_speaker_id;
  },
  findPlayableSample: R
};
export {
  F as __test,
  $ as default
};
