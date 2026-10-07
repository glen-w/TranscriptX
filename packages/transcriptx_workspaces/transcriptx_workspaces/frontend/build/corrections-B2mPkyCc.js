import { P as u, F as f } from "./constants-dt4zPgAn.js";
const d = /* @__PURE__ */ new WeakMap();
function k() {
  return typeof crypto < "u" && "randomUUID" in crypto ? crypto.randomUUID().replace(/-/g, "") : `a${Date.now().toString(16)}${Math.random().toString(16).slice(2)}`;
}
function o(r, t) {
  const i = r.querySelector(t);
  if (!i) throw new Error(`Missing element: ${t}`);
  return i;
}
function p(r) {
  return r instanceof HTMLElement ? r.tagName === "INPUT" || r.tagName === "TEXTAREA" || !!r.isContentEditable : !1;
}
function l(r, t, i, c = {}, n = {}) {
  if (n.mutating && r.mutating) return;
  const e = t.active, a = {
    protocol_version: u,
    frontend_build_id: f,
    action_id: k(),
    action_seq: ++r.actionSeq,
    session_id: t.session_id,
    expected_session_revision: t.session_revision,
    expected_candidate_revision: (e == null ? void 0 : e.revision) ?? null,
    candidate_id: (e == null ? void 0 : e.id) ?? t.active_candidate_id,
    action: i,
    payload: c
  };
  (t.protocol_version !== u || t.frontend_build_id !== f) && (a.action = "protocol_mismatch", a.payload = {
    got_protocol: t.protocol_version,
    got_build: t.frontend_build_id
  }), n.mutating && (r.mutating = !0), r.setTriggerValue("command", a), r.setStateValue("ack_seq", a.action_seq);
}
function v(r, t, i) {
  const c = o(r, ".tx-corr-list");
  c.replaceChildren();
  const n = t.active_candidate_id;
  for (const e of t.candidates || []) {
    const a = document.createElement("button");
    a.type = "button", a.className = "tx-corr-cand", e.id === n && a.setAttribute("aria-current", "true");
    const s = e.viewer ? "[viewer] " : "";
    a.textContent = `${s}${e.kind} — ${e.wrong_text} → ${e.right_text}`, a.addEventListener("click", () => {
      l(i, t, "select_candidate", { candidate_id: e.id });
    }), c.appendChild(a);
  }
}
function S(r, t, i) {
  var _, x;
  const c = o(r, ".tx-corr-status");
  c.textContent = ((_ = t.ui) == null ? void 0 : _.status) || "", t.ack && t.ack.action_seq >= i.lastAckSeq && (i.lastAckSeq = t.ack.action_seq, i.mutating = !1, t.ack.status === "rejected_protocol" && (c.textContent = t.ack.message || "Protocol mismatch — reload Corrections Studio.")), v(r, t, i);
  const n = o(r, ".tx-corr-draft"), e = t.active, a = o(r, ".tx-corr-wrong"), s = o(r, ".tx-corr-kind");
  e ? (s.textContent = `${e.kind} · ${e.status}`, a.textContent = `${e.wrong_text} → ${e.right_text}`, document.activeElement !== n && (n.value = e.right_text)) : (a.textContent = "Select a candidate.", s.textContent = "", document.activeElement !== n && (n.value = ""));
  const m = !!((x = t.ui) != null && x.disabled || i.mutating || !e);
  for (const g of [
    ".tx-corr-accept",
    ".tx-corr-reject",
    ".tx-corr-skip",
    ".tx-corr-save-draft"
  ])
    o(r, g).disabled = m;
  i.lastDataRef = t;
}
function E(r, t) {
  const i = {
    wired: !0,
    actionSeq: 0,
    lastAckSeq: 0,
    mutating: !1,
    lastDataRef: null,
    setTriggerValue: r.setTriggerValue,
    setStateValue: r.setStateValue
  };
  o(t, ".tx-corr-accept").addEventListener("click", () => {
    const n = i.lastDataRef;
    if (!n) return;
    const e = o(t, ".tx-corr-draft").value;
    l(
      i,
      n,
      "accept",
      { review_target_raw: e },
      { mutating: !0 }
    );
  }), o(t, ".tx-corr-reject").addEventListener("click", () => {
    const n = i.lastDataRef;
    n && l(i, n, "reject", {}, { mutating: !0 });
  }), o(t, ".tx-corr-skip").addEventListener("click", () => {
    const n = i.lastDataRef;
    n && l(i, n, "skip", {}, { mutating: !0 });
  }), o(t, ".tx-corr-save-draft").addEventListener(
    "click",
    () => {
      const n = i.lastDataRef;
      if (!n) return;
      const e = o(t, ".tx-corr-draft").value;
      l(
        i,
        n,
        "edit_draft",
        { right_text: e },
        { mutating: !0 }
      );
    }
  );
  const c = t.querySelector(".tx-corr-root") || t;
  return c.hasAttribute("tabindex") || c.setAttribute("tabindex", "0"), c.addEventListener("keydown", (n) => {
    p(n.target) || !i.lastDataRef || (n.key === "a" ? (n.preventDefault(), o(t, ".tx-corr-accept").click()) : n.key === "r" ? (n.preventDefault(), o(t, ".tx-corr-reject").click()) : n.key === "s" && (n.preventDefault(), o(t, ".tx-corr-skip").click()));
  }), i;
}
const D = (r) => {
  var a, s;
  const { parentElement: t, data: i } = r, c = t, n = ((a = c.querySelector) == null ? void 0 : a.call(c, ".tx-corr-root")) || ((s = c.querySelector) == null ? void 0 : s.call(c, ".tx-corr-root")) || c;
  let e = d.get(c);
  return e ? (e.setTriggerValue = r.setTriggerValue, e.setStateValue = r.setStateValue) : (e = E(r, n), d.set(c, e)), S(n, i, e), () => {
    d.delete(c);
  };
}, b = {
  FRONTEND_BUILD_ID: f,
  PROTOCOL_VERSION: u,
  isTypingTarget: p
};
export {
  b as __test,
  D as default
};
