import { P as u, F as f } from "./constants-dt4zPgAn.js";
const d = /* @__PURE__ */ new WeakMap();
function m() {
  return typeof crypto < "u" && "randomUUID" in crypto ? crypto.randomUUID().replace(/-/g, "") : `a${Date.now().toString(16)}${Math.random().toString(16).slice(2)}`;
}
function o(i, t) {
  const r = i.querySelector(t);
  if (!r) throw new Error(`Missing element: ${t}`);
  return r;
}
function l(i, t, r, c = {}, n = {}) {
  if (n.mutating && i.mutating) return;
  const e = t.active, a = {
    protocol_version: u,
    frontend_build_id: f,
    action_id: m(),
    action_seq: ++i.actionSeq,
    session_id: t.session_id,
    expected_session_revision: t.session_revision,
    expected_candidate_revision: (e == null ? void 0 : e.revision) ?? null,
    candidate_id: (e == null ? void 0 : e.id) ?? t.active_candidate_id,
    action: r,
    payload: c
  };
  (t.protocol_version !== u || t.frontend_build_id !== f) && (a.action = "protocol_mismatch", a.payload = {
    got_protocol: t.protocol_version,
    got_build: t.frontend_build_id
  }), n.mutating && (i.mutating = !0), i.setTriggerValue("command", a), i.setStateValue("ack_seq", a.action_seq);
}
function k(i, t, r) {
  const c = o(i, ".tx-corr-list");
  c.replaceChildren();
  const n = t.active_candidate_id;
  for (const e of t.candidates || []) {
    const a = document.createElement("button");
    a.type = "button", a.className = "tx-corr-cand", e.id === n && a.setAttribute("aria-current", "true");
    const s = e.viewer ? "[viewer] " : "";
    a.textContent = `${s}${e.kind} — ${e.wrong_text} → ${e.right_text}`, a.addEventListener("click", () => {
      l(r, t, "select_candidate", { candidate_id: e.id });
    }), c.appendChild(a);
  }
}
function v(i, t, r) {
  var _, x;
  const c = o(i, ".tx-corr-status");
  c.textContent = ((_ = t.ui) == null ? void 0 : _.status) || "", t.ack && t.ack.action_seq >= r.lastAckSeq && (r.lastAckSeq = t.ack.action_seq, r.mutating = !1, t.ack.status === "rejected_protocol" && (c.textContent = t.ack.message || "Protocol mismatch — reload Corrections Studio.")), k(i, t, r);
  const n = o(i, ".tx-corr-draft"), e = t.active, a = o(i, ".tx-corr-wrong"), s = o(i, ".tx-corr-kind");
  e ? (s.textContent = `${e.kind} · ${e.status}`, a.textContent = `${e.wrong_text} → ${e.right_text}`, document.activeElement !== n && (n.value = e.right_text)) : (a.textContent = "Select a candidate.", s.textContent = "", document.activeElement !== n && (n.value = ""));
  const g = !!((x = t.ui) != null && x.disabled || r.mutating || !e);
  for (const p of [
    ".tx-corr-accept",
    ".tx-corr-reject",
    ".tx-corr-skip",
    ".tx-corr-save-draft"
  ])
    o(i, p).disabled = g;
  r.lastDataRef = t;
}
function S(i, t) {
  const r = {
    wired: !0,
    actionSeq: 0,
    lastAckSeq: 0,
    mutating: !1,
    lastDataRef: null,
    setTriggerValue: i.setTriggerValue,
    setStateValue: i.setStateValue
  };
  o(t, ".tx-corr-accept").addEventListener("click", () => {
    const n = r.lastDataRef;
    if (!n) return;
    const e = o(t, ".tx-corr-draft").value;
    l(
      r,
      n,
      "accept",
      { review_target_raw: e },
      { mutating: !0 }
    );
  }), o(t, ".tx-corr-reject").addEventListener("click", () => {
    const n = r.lastDataRef;
    n && l(r, n, "reject", {}, { mutating: !0 });
  }), o(t, ".tx-corr-skip").addEventListener("click", () => {
    const n = r.lastDataRef;
    n && l(r, n, "skip", {}, { mutating: !0 });
  }), o(t, ".tx-corr-save-draft").addEventListener(
    "click",
    () => {
      const n = r.lastDataRef;
      if (!n) return;
      const e = o(t, ".tx-corr-draft").value;
      l(
        r,
        n,
        "edit_draft",
        { right_text: e },
        { mutating: !0 }
      );
    }
  );
  const c = t.querySelector(".tx-corr-root") || t;
  return c.hasAttribute("tabindex") || c.setAttribute("tabindex", "0"), c.addEventListener("keydown", (n) => {
    const e = n.target;
    e && (e.tagName === "INPUT" || e.tagName === "TEXTAREA" || e.isContentEditable) || !r.lastDataRef || (n.key === "a" ? (n.preventDefault(), o(t, ".tx-corr-accept").click()) : n.key === "r" ? (n.preventDefault(), o(t, ".tx-corr-reject").click()) : n.key === "s" && (n.preventDefault(), o(t, ".tx-corr-skip").click()));
  }), r;
}
const E = (i) => {
  var a, s;
  const { parentElement: t, data: r } = i, c = t, n = ((a = c.querySelector) == null ? void 0 : a.call(c, ".tx-corr-root")) || ((s = c.querySelector) == null ? void 0 : s.call(c, ".tx-corr-root")) || c;
  let e = d.get(c);
  return e ? (e.setTriggerValue = i.setTriggerValue, e.setStateValue = i.setStateValue) : (e = S(i, n), d.set(c, e)), v(n, r, e), () => {
    d.delete(c);
  };
}, b = {
  FRONTEND_BUILD_ID: f,
  PROTOCOL_VERSION: u
};
export {
  b as __test,
  E as default
};
