/**
 * Corrections Studio CCv2 review pane (Theme C).
 *
 * Candidate list + detail + accept/reject/skip/edit draft stay in the browser.
 * Generate / apply_export remain Streamlit chrome (server-authoritative).
 */

import type {
  FrontendRenderer,
  FrontendRendererArgs,
} from "@streamlit/component-v2-lib";

import { FRONTEND_BUILD_ID, PROTOCOL_VERSION } from "./constants";

export type CorrectionsState = {
  ack_seq: number;
  command: CorrectionsCommandEnvelope | null;
};

export type CorrectionsCommandEnvelope = {
  protocol_version: string;
  frontend_build_id: string;
  action_id: string;
  action_seq: number;
  session_id: string;
  expected_session_revision: string;
  expected_candidate_revision: string | null;
  candidate_id: string | null;
  action: string;
  payload: Record<string, unknown>;
};

export type CandidateRow = {
  id: string;
  kind: string;
  status: string;
  wrong_text: string;
  right_text: string;
  confidence: number;
  revision: string;
  sources?: string[];
  viewer?: boolean;
};

export type CorrectionsData = {
  protocol_version: string;
  frontend_build_id: string;
  session_id: string;
  session_revision: string;
  active_candidate_id: string | null;
  candidates: CandidateRow[];
  active?: {
    id: string;
    kind: string;
    status: string;
    wrong_text: string;
    right_text: string;
    revision: string;
    rationale?: string | null;
  } | null;
  ack?: {
    action_id: string;
    action_seq: number;
    status: string;
    message?: string | null;
  } | null;
  ui?: { status?: string; disabled?: boolean };
};

type HostElement = HTMLElement | ShadowRoot;

type InstanceState = {
  wired: boolean;
  actionSeq: number;
  lastAckSeq: number;
  mutating: boolean;
  lastDataRef: CorrectionsData | null;
  setTriggerValue: FrontendRendererArgs<
    CorrectionsState,
    CorrectionsData
  >["setTriggerValue"];
  setStateValue: FrontendRendererArgs<
    CorrectionsState,
    CorrectionsData
  >["setStateValue"];
};

const instances = new WeakMap<object, InstanceState>();

function newActionId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID().replace(/-/g, "");
  }
  return `a${Date.now().toString(16)}${Math.random().toString(16).slice(2)}`;
}

function qs<T extends Element>(root: ParentNode, sel: string): T {
  const el = root.querySelector(sel);
  if (!el) throw new Error(`Missing element: ${sel}`);
  return el as T;
}

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return (
    target.tagName === "INPUT" ||
    target.tagName === "TEXTAREA" ||
    Boolean(target.isContentEditable)
  );
}

function fireCommand(
  state: InstanceState,
  data: CorrectionsData,
  action: string,
  payload: Record<string, unknown> = {},
  opts: { mutating?: boolean } = {},
): void {
  if (opts.mutating && state.mutating) return;
  const active = data.active;
  const envelope: CorrectionsCommandEnvelope = {
    protocol_version: PROTOCOL_VERSION,
    frontend_build_id: FRONTEND_BUILD_ID,
    action_id: newActionId(),
    action_seq: ++state.actionSeq,
    session_id: data.session_id,
    expected_session_revision: data.session_revision,
    expected_candidate_revision: active?.revision ?? null,
    candidate_id: active?.id ?? data.active_candidate_id,
    action,
    payload,
  };
  if (
    data.protocol_version !== PROTOCOL_VERSION ||
    data.frontend_build_id !== FRONTEND_BUILD_ID
  ) {
    envelope.action = "protocol_mismatch";
    envelope.payload = {
      got_protocol: data.protocol_version,
      got_build: data.frontend_build_id,
    };
  }
  if (opts.mutating) state.mutating = true;
  state.setTriggerValue("command", envelope);
  state.setStateValue("ack_seq", envelope.action_seq);
}

function renderList(
  root: Element,
  data: CorrectionsData,
  state: InstanceState,
): void {
  const list = qs<HTMLElement>(root, ".tx-corr-list");
  list.replaceChildren();
  const activeId = data.active_candidate_id;
  for (const c of data.candidates || []) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "tx-corr-cand";
    if (c.id === activeId) btn.setAttribute("aria-current", "true");
    const prefix = c.viewer ? "[viewer] " : "";
    btn.textContent = `${prefix}${c.kind} — ${c.wrong_text} → ${c.right_text}`;
    btn.addEventListener("click", () => {
      fireCommand(state, data, "select_candidate", { candidate_id: c.id });
    });
    list.appendChild(btn);
  }
}

function applyData(
  root: Element,
  data: CorrectionsData,
  state: InstanceState,
): void {
  const status = qs<HTMLElement>(root, ".tx-corr-status");
  status.textContent = data.ui?.status || "";
  if (data.ack && data.ack.action_seq >= state.lastAckSeq) {
    state.lastAckSeq = data.ack.action_seq;
    state.mutating = false;
    if (data.ack.status === "rejected_protocol") {
      status.textContent =
        data.ack.message || "Protocol mismatch — reload Corrections Studio.";
    }
  }
  renderList(root, data, state);
  const draft = qs<HTMLInputElement>(root, ".tx-corr-draft");
  const active = data.active;
  const wrong = qs<HTMLElement>(root, ".tx-corr-wrong");
  const kind = qs<HTMLElement>(root, ".tx-corr-kind");
  if (!active) {
    wrong.textContent = "Select a candidate.";
    kind.textContent = "";
    if (document.activeElement !== draft) draft.value = "";
  } else {
    kind.textContent = `${active.kind} · ${active.status}`;
    wrong.textContent = `${active.wrong_text} → ${active.right_text}`;
    if (document.activeElement !== draft) {
      draft.value = active.right_text;
    }
  }
  const disabled = Boolean(data.ui?.disabled || state.mutating || !active);
  for (const sel of [
    ".tx-corr-accept",
    ".tx-corr-reject",
    ".tx-corr-skip",
    ".tx-corr-save-draft",
  ]) {
    qs<HTMLButtonElement>(root, sel).disabled = disabled;
  }
  state.lastDataRef = data;
}

function wireOnce(
  args: FrontendRendererArgs<CorrectionsState, CorrectionsData>,
  root: Element,
): InstanceState {
  const state: InstanceState = {
    wired: true,
    actionSeq: 0,
    lastAckSeq: 0,
    mutating: false,
    lastDataRef: null,
    setTriggerValue: args.setTriggerValue,
    setStateValue: args.setStateValue,
  };
  qs<HTMLButtonElement>(root, ".tx-corr-accept").addEventListener("click", () => {
    const data = state.lastDataRef;
    if (!data) return;
    const draft = qs<HTMLInputElement>(root, ".tx-corr-draft").value;
    fireCommand(
      state,
      data,
      "accept",
      { review_target_raw: draft },
      { mutating: true },
    );
  });
  qs<HTMLButtonElement>(root, ".tx-corr-reject").addEventListener("click", () => {
    const data = state.lastDataRef;
    if (!data) return;
    fireCommand(state, data, "reject", {}, { mutating: true });
  });
  qs<HTMLButtonElement>(root, ".tx-corr-skip").addEventListener("click", () => {
    const data = state.lastDataRef;
    if (!data) return;
    fireCommand(state, data, "skip", {}, { mutating: true });
  });
  qs<HTMLButtonElement>(root, ".tx-corr-save-draft").addEventListener(
    "click",
    () => {
      const data = state.lastDataRef;
      if (!data) return;
      const draft = qs<HTMLInputElement>(root, ".tx-corr-draft").value;
      fireCommand(
        state,
        data,
        "edit_draft",
        { right_text: draft },
        { mutating: true },
      );
    },
  );
  const keyHost =
    (root.querySelector(".tx-corr-root") as HTMLElement | null) ||
    (root as HTMLElement);
  if (!keyHost.hasAttribute("tabindex")) keyHost.setAttribute("tabindex", "0");
  keyHost.addEventListener("keydown", (ev: KeyboardEvent) => {
    if (isTypingTarget(ev.target)) {
      return;
    }
    const data = state.lastDataRef;
    if (!data) return;
    if (ev.key === "a") {
      ev.preventDefault();
      qs<HTMLButtonElement>(root, ".tx-corr-accept").click();
    } else if (ev.key === "r") {
      ev.preventDefault();
      qs<HTMLButtonElement>(root, ".tx-corr-reject").click();
    } else if (ev.key === "s") {
      ev.preventDefault();
      qs<HTMLButtonElement>(root, ".tx-corr-skip").click();
    }
  });
  return state;
}

const CorrectionsWorkspace: FrontendRenderer<
  CorrectionsState,
  CorrectionsData
> = (args) => {
  const { parentElement, data } = args;
  const host: HostElement = parentElement;
  const rootEl =
    (host as HTMLElement).querySelector?.(".tx-corr-root") ||
    (host as ShadowRoot).querySelector?.(".tx-corr-root") ||
    (host as unknown as Element);
  let state = instances.get(host);
  if (!state) {
    state = wireOnce(args, rootEl as Element);
    instances.set(host, state);
  } else {
    state.setTriggerValue = args.setTriggerValue;
    state.setStateValue = args.setStateValue;
  }
  applyData(rootEl as Element, data, state);
  return () => {
    instances.delete(host);
  };
};

export default CorrectionsWorkspace;

export const __test = {
  FRONTEND_BUILD_ID,
  PROTOCOL_VERSION,
  isTypingTarget,
};
