const _ = /* @__PURE__ */ new WeakMap(), m = "tx-workspaces-0.1.0", k = "1", y = 8e6;
function g() {
  return typeof crypto < "u" && "randomUUID" in crypto ? crypto.randomUUID().replace(/-/g, "") : `a${Date.now().toString(16)}${Math.random().toString(16).slice(2)}`;
}
function l(n, e) {
  const r = n.querySelector(e);
  if (!r) throw new Error(`Missing element: ${e}`);
  return r;
}
function b(n) {
  for (const e of n.blobUrls.values())
    URL.revokeObjectURL(e);
  n.blobUrls.clear(), n.blobBytes = 0;
}
function v(n, e, r, o) {
  const i = n.blobUrls.get(e);
  if (i) return i;
  try {
    const a = atob(r);
    if (n.blobBytes + a.length > o)
      return null;
    const s = new Uint8Array(a.length);
    for (let t = 0; t < a.length; t++) s[t] = a.charCodeAt(t);
    const c = URL.createObjectURL(new Blob([s], { type: "audio/mpeg" }));
    return n.blobUrls.set(e, c), n.blobBytes += a.length, c;
  } catch {
    return null;
  }
}
function f(n, e, r, o = {}, i = {}) {
  const a = !!i.mutating;
  if (a && n.mutating) return;
  if (e.protocol_version !== k || e.frontend_build_id !== m) {
    n.setTriggerValue("command", {
      protocol_version: k,
      frontend_build_id: m,
      action_id: g(),
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
  a && (n.mutating = !0);
  const s = {
    protocol_version: k,
    frontend_build_id: m,
    action_id: g(),
    action_seq: ++n.actionSeq,
    transcript_id: e.transcript_id,
    transcript_revision: e.transcript_revision,
    expected_speaker_id: n.optimisticSpeakerId ?? e.active_speaker_id,
    expected_mapping_revision: e.mapping_revision,
    audio_fingerprint: e.audio_fingerprint ?? null,
    action: r,
    payload: o
  };
  n.setTriggerValue("command", s), n.setStateValue("ack_seq", s.action_seq);
}
function x(n, e, r) {
  const o = l(n, ".tx-sid-speakers");
  o.replaceChildren();
  const i = r.optimisticSpeakerId ?? e.active_speaker_id;
  for (const a of e.speakers || []) {
    const s = document.createElement("button");
    s.type = "button", s.className = "tx-sid-speaker-btn", s.textContent = a.label, a.id === i && s.setAttribute("aria-current", "true"), s.addEventListener("click", () => {
      r.optimisticSpeakerId = a.id, f(r, e, "navigate_jump", {
        target_speaker_id: a.id
      }), x(n, e, r);
    }), o.appendChild(s);
  }
}
function h(n, e, r) {
  var a;
  const o = l(n, ".tx-sid-samples");
  o.replaceChildren();
  const i = ((a = e.budgets) == null ? void 0 : a.max_blob_bytes) ?? y;
  for (const s of e.samples || []) {
    const c = document.createElement("li");
    c.className = "tx-sid-sample";
    const t = document.createElement("button");
    t.type = "button", t.className = "tx-sid-sample-play", t.textContent = "▶", t.setAttribute("aria-label", "Play sample"), t.addEventListener("click", () => {
      if (s.clip_b64) {
        const u = v(r, s.clip_id, s.clip_b64, i);
        if (u) {
          r.audio.src !== u && (r.audio.src = u), r.audio.play().catch(() => {
          }), l(n, ".tx-sid-clip-status").textContent = "";
          return;
        }
      }
      l(n, ".tx-sid-clip-status").textContent = s.clip_status === "inflight" || s.clip_status === "pending" ? "Preparing clip…" : "Clip pending…", f(r, e, "enqueue_clip", {
        clip_id: s.clip_id,
        start: s.start,
        end: s.end
      });
    });
    const d = document.createElement("div");
    d.textContent = s.text || "", c.append(t, d), o.appendChild(c);
  }
}
function S(n, e, r) {
  var c, t, d;
  l(n, ".tx-sid-title").textContent = `Speaker ${e.active_speaker_id}`;
  const o = l(n, ".tx-sid-status");
  o.textContent = ((c = e.ui) == null ? void 0 : c.status) || "", e.ack && e.ack.action_seq >= r.lastAckSeq && (r.lastAckSeq = e.ack.action_seq, e.ack.action_seq >= r.actionSeq - 0, (e.ack.status === "ok" || e.ack.status === "partial" || e.ack.status === "error" || e.ack.status === "rejected_stale" || e.ack.status === "rejected_protocol") && (r.mutating = !1, r.optimisticSpeakerId = null), e.ack.status === "rejected_protocol" && (o.textContent = e.ack.message || "Protocol mismatch — reload or use classic UI."));
  const i = l(n, ".tx-sid-name-input");
  document.activeElement !== i && (i.value = e.draft_name || "");
  const a = l(n, ".tx-sid-link-profile");
  a.disabled = !(e.link_profile_allowed ?? ((t = e.capabilities) == null ? void 0 : t.profile_link));
  const s = !!((d = e.ui) != null && d.disabled || r.mutating);
  for (const u of [".tx-sid-save", ".tx-sid-ignore", ".tx-sid-prev", ".tx-sid-next"])
    l(n, u).disabled = s;
  x(n, e, r), h(n, e, r), r.lastDataRef = e;
}
function E(n, e, r) {
  const i = {
    wired: !0,
    audio: l(e, ".tx-sid-audio"),
    blobUrls: /* @__PURE__ */ new Map(),
    blobBytes: 0,
    lastAckSeq: 0,
    actionSeq: 0,
    mutating: !1,
    optimisticSpeakerId: null,
    retryTimers: [],
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
    setTriggerValue: r.setTriggerValue,
    setStateValue: r.setStateValue,
    host: n
  };
  (() => {
    i.handlers.onSave = () => {
      const t = i.lastDataRef;
      if (!t) return;
      const d = l(e, ".tx-sid-name-input").value.trim(), u = l(e, ".tx-sid-link-profile").checked;
      f(
        i,
        t,
        "save_name",
        { display_name: d, link_profile: u },
        { mutating: !0 }
      );
    }, i.handlers.onIgnore = () => {
      const t = i.lastDataRef;
      t && f(i, t, "ignore_toggle", {}, { mutating: !0 });
    }, i.handlers.onPrev = () => {
      const t = i.lastDataRef;
      t && f(i, t, "navigate_prev");
    }, i.handlers.onNext = () => {
      const t = i.lastDataRef;
      t && f(i, t, "navigate_next");
    }, i.handlers.onKey = (t) => {
      const d = t.target;
      if (d && (d.tagName === "INPUT" || d.tagName === "TEXTAREA" || d.isContentEditable))
        return;
      if (!e.contains(document.activeElement) && document.activeElement !== e) {
        const p = i.host;
        if (!("contains" in p ? p.contains(document.activeElement) : !1)) return;
      }
      if (i.lastDataRef) {
        if (t.key === "Enter")
          t.preventDefault(), i.handlers.onSave();
        else if (t.key === " " || t.code === "Space")
          t.preventDefault(), i.audio.paused ? i.audio.play().catch(() => {
          }) : i.audio.pause();
        else if (t.key === "j" || t.key === "ArrowDown")
          t.preventDefault(), i.handlers.onNext();
        else if (t.key === "k" || t.key === "ArrowUp")
          t.preventDefault(), i.handlers.onPrev();
        else if (t.key === "i")
          t.preventDefault(), i.handlers.onIgnore();
        else if (t.key === "?") {
          const p = l(e, ".tx-sid-help");
          p.hidden = !p.hidden, p.textContent = "Shortcuts (workspace focused): j/↓ next · k/↑ prev · Space play/pause · Enter save · i ignore · ? help";
        }
      }
    };
  })(), l(e, ".tx-sid-save").addEventListener(
    "click",
    () => i.handlers.onSave()
  ), l(e, ".tx-sid-ignore").addEventListener(
    "click",
    () => i.handlers.onIgnore()
  ), l(e, ".tx-sid-prev").addEventListener(
    "click",
    () => i.handlers.onPrev()
  ), l(e, ".tx-sid-next").addEventListener(
    "click",
    () => i.handlers.onNext()
  ), ("addEventListener" in n ? n : e).addEventListener(
    "keydown",
    (t) => i.handlers.onKey(t)
  );
  const c = e.querySelector(".tx-sid-root") || e;
  return c.hasAttribute("tabindex") || c.setAttribute("tabindex", "0"), i;
}
const q = (n) => {
  var s, c;
  const { parentElement: e, data: r } = n, o = e, i = ((s = o.querySelector) == null ? void 0 : s.call(o, ".tx-sid-root")) || ((c = o.querySelector) == null ? void 0 : c.call(o, ".tx-sid-root")) || o;
  let a = _.get(o);
  return a ? (a.setTriggerValue = n.setTriggerValue, a.setStateValue = n.setStateValue) : (a = E(o, i, n), _.set(o, a)), S(i, r, a), () => {
    const t = _.get(o);
    if (t) {
      for (const d of t.retryTimers) window.clearTimeout(d);
      t.retryTimers = [], b(t), t.audio.removeAttribute("src"), t.audio.load(), _.delete(o);
    }
  };
}, U = {
  instances: _,
  ensureBlobUrl: v,
  revokeAllBlobs: b,
  PROTOCOL_VERSION: k,
  FRONTEND_BUILD_ID: m
};
export {
  U as __test,
  q as default
};
