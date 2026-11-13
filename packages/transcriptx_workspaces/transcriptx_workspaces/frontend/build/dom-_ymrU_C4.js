const a = "tx-workspaces-0.3.0", s = "1";
function o(n = document) {
  var i;
  let e = n.activeElement;
  if (!e) return null;
  for (; e; ) {
    const t = e.shadowRoot;
    if (t != null && t.activeElement) {
      e = t.activeElement;
      continue;
    }
    if (e instanceof HTMLIFrameElement)
      try {
        const c = (i = e.contentDocument) == null ? void 0 : i.activeElement;
        if (c && c !== e) {
          e = c;
          continue;
        }
      } catch {
      }
    break;
  }
  return e;
}
function l(n, e = document) {
  return o(e) === n;
}
function m(n) {
  return n instanceof HTMLElement ? n.tagName === "INPUT" || n.tagName === "TEXTAREA" || n.tagName === "SELECT" || !!n.isContentEditable : !1;
}
export {
  a as F,
  s as P,
  l as e,
  m as i
};
