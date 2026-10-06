const s = /* @__PURE__ */ new WeakMap();
function u(r, o) {
  const e = r.querySelector(o);
  if (!e) throw new Error(`Missing element: ${o}`);
  return e;
}
function l(r, o, e) {
  const i = Math.min(o, e), t = Math.max(o, e);
  return r.filter((n) => n.i >= i && n.i <= t).map((n) => n.text).join(" ");
}
function c(r, o) {
  r.querySelectorAll(".tx-vedit-word").forEach((t) => {
    const n = Number(t.dataset.i);
    o != null && n >= Math.min(o.i0, o.i1) && n <= Math.max(o.i0, o.i1) ? t.setAttribute("aria-selected", "true") : t.removeAttribute("aria-selected");
  });
  const i = u(r, ".tx-vedit-caption");
  i.textContent = o ? `Selected: ${o.text}` : "Click and drag to select a word span.";
}
function m(r, o, e) {
  const i = u(r, ".tx-vedit-words");
  i.replaceChildren(), e.words = o.words || [];
  for (const t of e.words) {
    const n = document.createElement("span");
    n.className = "tx-vedit-word", n.dataset.i = String(t.i), n.textContent = t.text, t.low_conf && n.classList.add("tx-vedit-low"), n.addEventListener("mousedown", (a) => {
      a.preventDefault(), e.dragFrom = t.i;
      const d = { i0: t.i, i1: t.i, text: l(e.words, t.i, t.i) };
      e.lastSelection = d, e.setStateValue("selection", d), c(r, d);
    }), n.addEventListener("mouseenter", () => {
      if (e.dragFrom == null) return;
      const a = {
        i0: e.dragFrom,
        i1: t.i,
        text: l(e.words, e.dragFrom, t.i)
      };
      e.lastSelection = a, e.setStateValue("selection", a), c(r, a);
    }), i.appendChild(n), i.appendChild(document.createTextNode(" "));
  }
}
function x(r, o) {
  const e = {
    wired: !0,
    dragFrom: null,
    words: [],
    lastSelection: null,
    setStateValue: r.setStateValue
  }, i = () => {
    e.dragFrom = null;
  };
  window.addEventListener("mouseup", i);
  const t = o.querySelector(".tx-vedit-root") || o;
  return t.hasAttribute("tabindex") || t.setAttribute("tabindex", "0"), e;
}
const w = (r) => {
  var a, d;
  const { parentElement: o, data: e } = r, i = o, t = ((a = i.querySelector) == null ? void 0 : a.call(i, ".tx-vedit-root")) || ((d = i.querySelector) == null ? void 0 : d.call(i, ".tx-vedit-root")) || i;
  let n = s.get(i);
  return n ? n.setStateValue = r.setStateValue : (n = x(r, t), s.set(i, n)), m(t, e, n), c(t, n.lastSelection), () => {
    s.delete(i);
  };
};
export {
  w as default
};
