/**
 * Transcript Correct-mode word-span selection (Theme C richer edit).
 *
 * Selection is browser state (setStateValue). Propose/apply stay Streamlit.
 */

import type {
  FrontendRenderer,
  FrontendRendererArgs,
} from "@streamlit/component-v2-lib";

export type WordTok = {
  i: number;
  text: string;
  low_conf?: boolean;
};

export type ViewerEditData = {
  words: WordTok[];
  segment_id: string;
};

export type ViewerSelection = {
  i0: number;
  i1: number;
  text: string;
} | null;

export type ViewerEditState = {
  selection: ViewerSelection;
};

type HostElement = HTMLElement | ShadowRoot;

type InstanceState = {
  wired: boolean;
  dragFrom: number | null;
  words: WordTok[];
  lastSelection: ViewerSelection;
  setStateValue: FrontendRendererArgs<
    ViewerEditState,
    ViewerEditData
  >["setStateValue"];
};

const instances = new WeakMap<object, InstanceState>();

function qs<T extends Element>(root: ParentNode, sel: string): T {
  const el = root.querySelector(sel);
  if (!el) throw new Error(`Missing element: ${sel}`);
  return el as T;
}

function spanText(words: WordTok[], i0: number, i1: number): string {
  const a = Math.min(i0, i1);
  const b = Math.max(i0, i1);
  return words
    .filter((w) => w.i >= a && w.i <= b)
    .map((w) => w.text)
    .join(" ");
}

function paintSelection(root: Element, sel: ViewerSelection): void {
  const nodes = root.querySelectorAll<HTMLElement>(".tx-vedit-word");
  nodes.forEach((el) => {
    const i = Number(el.dataset.i);
    const on =
      sel != null && i >= Math.min(sel.i0, sel.i1) && i <= Math.max(sel.i0, sel.i1);
    if (on) el.setAttribute("aria-selected", "true");
    else el.removeAttribute("aria-selected");
  });
  const cap = qs<HTMLElement>(root, ".tx-vedit-caption");
  cap.textContent = sel
    ? `Selected: ${sel.text}`
    : "Click and drag to select a word span.";
}

function renderWords(root: Element, data: ViewerEditData, state: InstanceState): void {
  const host = qs<HTMLElement>(root, ".tx-vedit-words");
  host.replaceChildren();
  state.words = data.words || [];
  for (const w of state.words) {
    const span = document.createElement("span");
    span.className = "tx-vedit-word";
    span.dataset.i = String(w.i);
    span.textContent = w.text;
    if (w.low_conf) span.classList.add("tx-vedit-low");
    span.addEventListener("mousedown", (ev) => {
      ev.preventDefault();
      state.dragFrom = w.i;
      const sel = { i0: w.i, i1: w.i, text: spanText(state.words, w.i, w.i) };
      state.lastSelection = sel;
      state.setStateValue("selection", sel);
      paintSelection(root, sel);
    });
    span.addEventListener("mouseenter", () => {
      if (state.dragFrom == null) return;
      const sel = {
        i0: state.dragFrom,
        i1: w.i,
        text: spanText(state.words, state.dragFrom, w.i),
      };
      state.lastSelection = sel;
      state.setStateValue("selection", sel);
      paintSelection(root, sel);
    });
    host.appendChild(span);
    host.appendChild(document.createTextNode(" "));
  }
}

function wireOnce(
  args: FrontendRendererArgs<ViewerEditState, ViewerEditData>,
  root: Element,
): InstanceState {
  const state: InstanceState = {
    wired: true,
    dragFrom: null,
    words: [],
    lastSelection: null,
    setStateValue: args.setStateValue,
  };
  const up = () => {
    state.dragFrom = null;
  };
  window.addEventListener("mouseup", up);
  const focusHost =
    (root.querySelector(".tx-vedit-root") as HTMLElement | null) ||
    (root as HTMLElement);
  if (!focusHost.hasAttribute("tabindex")) focusHost.setAttribute("tabindex", "0");
  return state;
}

const ViewerEditWorkspace: FrontendRenderer<ViewerEditState, ViewerEditData> = (
  args,
) => {
  const { parentElement, data } = args;
  const host: HostElement = parentElement;
  const rootEl =
    (host as HTMLElement).querySelector?.(".tx-vedit-root") ||
    (host as ShadowRoot).querySelector?.(".tx-vedit-root") ||
    (host as unknown as Element);
  let inst = instances.get(host);
  if (!inst) {
    inst = wireOnce(args, rootEl as Element);
    instances.set(host, inst);
  } else {
    inst.setStateValue = args.setStateValue;
  }
  renderWords(rootEl as Element, data, inst);
  paintSelection(rootEl as Element, inst.lastSelection);
  return () => {
    instances.delete(host);
  };
};

export default ViewerEditWorkspace;
