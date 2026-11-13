/**
 * Focus helpers for CCv2 workspaces (shadow DOM + iframes).
 * Shell keyboard logic in transcriptx.web.shell mirrors resolveActiveElement.
 */

export function resolveActiveElement(doc: Document = document): Element | null {
  let el: Element | null = doc.activeElement;
  if (!el) return null;
  while (el) {
    const shadow: ShadowRoot | null = (el as HTMLElement).shadowRoot;
    if (shadow?.activeElement) {
      el = shadow.activeElement;
      continue;
    }
    if (el instanceof HTMLIFrameElement) {
      try {
        const inner: Element | null | undefined =
          el.contentDocument?.activeElement;
        if (inner && inner !== el) {
          el = inner;
          continue;
        }
      } catch {
        /* cross-origin iframe */
      }
    }
    break;
  }
  return el;
}

export function elementHasFocus(el: Element, doc: Document = document): boolean {
  return resolveActiveElement(doc) === el;
}

export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return (
    target.tagName === "INPUT" ||
    target.tagName === "TEXTAREA" ||
    target.tagName === "SELECT" ||
    Boolean(target.isContentEditable)
  );
}
