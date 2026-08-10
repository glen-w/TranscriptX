/**
 * Speaker ID CCv2 workspace frontend (Theme C).
 *
 * Lifecycle rules (Phase 0 gates):
 * - Per-instance state via WeakMap keyed by parentElement
 * - Idempotent event registration (bound once per instance)
 * - Never recreate the <audio> element on ordinary renderer calls
 * - Cleanup listeners, timers, retries, Blob URLs on unmount
 * - Playhead stays browser-local — never stream current_time via setStateValue
 */

import type {
  FrontendRenderer,
  FrontendRendererArgs,
} from "@streamlit/component-v2-lib";

export type WorkspaceState = {
  ack_seq: number;
  command: CommandEnvelope | null;
};

export type CommandEnvelope = {
  protocol_version: string;
  frontend_build_id: string;
  action_id: string;
  action_seq: number;
  transcript_id: string;
  transcript_revision: string | null;
  expected_speaker_id: string | null;
  expected_mapping_revision: string | null;
  audio_fingerprint: string | null;
  action: string;
  payload: Record<string, unknown>;
};

export type SampleRow = {
  clip_id: string;
  start: number;
  end: number;
  text: string;
  clip_b64?: string | null;
  clip_status?: string | null;
};

export type SpeakerRow = {
  id: string;
  label: string;
  named: boolean;
  ignored: boolean;
};

export type WorkspaceData = {
  protocol_version: string;
  frontend_build_id: string;
  transcript_id: string;
  transcript_revision: string;
  mapping_revision: string;
  audio_fingerprint?: string | null;
  active_speaker_id: string;
  speakers: SpeakerRow[];
  samples: SampleRow[];
  draft_name?: string;
  link_profile_allowed?: boolean;
  capabilities?: { ffmpeg?: boolean; profile_link?: boolean };
  ui?: { status?: string; disabled?: boolean; flash?: string | null };
  ack?: {
    action_id: string;
    action_seq: number;
    status: string;
    message?: string | null;
  } | null;
  budgets?: {
    max_blob_bytes?: number;
  };
};

type HostElement = HTMLElement | ShadowRoot;

type InstanceState = {
  wired: boolean;
  audio: HTMLAudioElement;
  blobUrls: Map<string, string>;
  blobBytes: number;
  lastAckSeq: number;
  actionSeq: number;
  mutating: boolean;
  optimisticSpeakerId: string | null;
  retryTimers: number[];
  handlers: {
    onSave: () => void;
    onIgnore: () => void;
    onPrev: () => void;
    onNext: () => void;
    onKey: (ev: KeyboardEvent) => void;
    onNameInput: () => void;
  };
  lastDataRef: WorkspaceData | null;
  setTriggerValue: FrontendRendererArgs<WorkspaceState, WorkspaceData>["setTriggerValue"];
  setStateValue: FrontendRendererArgs<WorkspaceState, WorkspaceData>["setStateValue"];
  host: HostElement;
};

const instances = new WeakMap<object, InstanceState>();
const FRONTEND_BUILD_ID = "tx-workspaces-0.1.0";
const PROTOCOL_VERSION = "1";
const DEFAULT_MAX_BLOB = 8_000_000;

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

function revokeAllBlobs(state: InstanceState): void {
  for (const url of state.blobUrls.values()) {
    URL.revokeObjectURL(url);
  }
  state.blobUrls.clear();
  state.blobBytes = 0;
}

function ensureBlobUrl(
  state: InstanceState,
  clipId: string,
  b64: string,
  maxBlob: number,
): string | null {
  const existing = state.blobUrls.get(clipId);
  if (existing) return existing;
  try {
    const bin = atob(b64);
    if (state.blobBytes + bin.length > maxBlob) {
      return null;
    }
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    const url = URL.createObjectURL(new Blob([bytes], { type: "audio/mpeg" }));
    state.blobUrls.set(clipId, url);
    state.blobBytes += bin.length;
    return url;
  } catch {
    return null;
  }
}

function fireCommand(
  state: InstanceState,
  data: WorkspaceData,
  action: string,
  payload: Record<string, unknown> = {},
  opts: { mutating?: boolean } = {},
): void {
  const mutating = Boolean(opts.mutating);
  if (mutating && state.mutating) return;
  if (
    data.protocol_version !== PROTOCOL_VERSION ||
    data.frontend_build_id !== FRONTEND_BUILD_ID
  ) {
    // Fail closed: ask Python to force reload/fallback via a special command.
    state.setTriggerValue("command", {
      protocol_version: PROTOCOL_VERSION,
      frontend_build_id: FRONTEND_BUILD_ID,
      action_id: newActionId(),
      action_seq: ++state.actionSeq,
      transcript_id: data.transcript_id,
      transcript_revision: data.transcript_revision,
      expected_speaker_id: data.active_speaker_id,
      expected_mapping_revision: data.mapping_revision,
      audio_fingerprint: data.audio_fingerprint ?? null,
      action: "protocol_mismatch",
      payload: {
        got_protocol: data.protocol_version,
        got_build: data.frontend_build_id,
      },
    } satisfies CommandEnvelope);
    return;
  }
  if (mutating) state.mutating = true;
  const envelope: CommandEnvelope = {
    protocol_version: PROTOCOL_VERSION,
    frontend_build_id: FRONTEND_BUILD_ID,
    action_id: newActionId(),
    action_seq: ++state.actionSeq,
    transcript_id: data.transcript_id,
    transcript_revision: data.transcript_revision,
    expected_speaker_id: state.optimisticSpeakerId ?? data.active_speaker_id,
    expected_mapping_revision: data.mapping_revision,
    audio_fingerprint: data.audio_fingerprint ?? null,
    action,
    payload,
  };
  state.setTriggerValue("command", envelope);
  state.setStateValue("ack_seq", envelope.action_seq);
}

function renderSpeakers(root: Element, data: WorkspaceData, state: InstanceState): void {
  const list = qs<HTMLElement>(root, ".tx-sid-speakers");
  list.replaceChildren();
  const active = state.optimisticSpeakerId ?? data.active_speaker_id;
  for (const sp of data.speakers || []) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "tx-sid-speaker-btn";
    btn.textContent = sp.label;
    if (sp.id === active) btn.setAttribute("aria-current", "true");
    btn.addEventListener("click", () => {
      state.optimisticSpeakerId = sp.id;
      fireCommand(state, data, "navigate_jump", {
        target_speaker_id: sp.id,
      });
      renderSpeakers(root, data, state);
    });
    list.appendChild(btn);
  }
}

function renderSamples(root: Element, data: WorkspaceData, state: InstanceState): void {
  const ol = qs<HTMLOListElement>(root, ".tx-sid-samples");
  ol.replaceChildren();
  const maxBlob = data.budgets?.max_blob_bytes ?? DEFAULT_MAX_BLOB;
  for (const sample of data.samples || []) {
    const li = document.createElement("li");
    li.className = "tx-sid-sample";
    const play = document.createElement("button");
    play.type = "button";
    play.className = "tx-sid-sample-play";
    play.textContent = "▶";
    play.setAttribute("aria-label", "Play sample");
    play.addEventListener("click", () => {
      if (sample.clip_b64) {
        const url = ensureBlobUrl(state, sample.clip_id, sample.clip_b64, maxBlob);
        if (url) {
          // Same <audio> element — only change src.
          if (state.audio.src !== url) {
            state.audio.src = url;
          }
          void state.audio.play().catch(() => undefined);
          qs<HTMLElement>(root, ".tx-sid-clip-status").textContent = "";
          return;
        }
      }
      qs<HTMLElement>(root, ".tx-sid-clip-status").textContent =
        sample.clip_status === "inflight" || sample.clip_status === "pending"
          ? "Preparing clip…"
          : "Clip pending…";
      fireCommand(state, data, "enqueue_clip", {
        clip_id: sample.clip_id,
        start: sample.start,
        end: sample.end,
      });
    });
    const text = document.createElement("div");
    text.textContent = sample.text || "";
    li.append(play, text);
    ol.appendChild(li);
  }
}

function applyData(root: Element, data: WorkspaceData, state: InstanceState): void {
  qs<HTMLElement>(root, ".tx-sid-title").textContent =
    `Speaker ${data.active_speaker_id}`;
  const status = qs<HTMLElement>(root, ".tx-sid-status");
  status.textContent = data.ui?.status || "";

  if (data.ack && data.ack.action_seq >= state.lastAckSeq) {
    state.lastAckSeq = data.ack.action_seq;
    if (data.ack.action_seq >= state.actionSeq - 0) {
      // Accept ack if not older than last applied.
    }
    if (
      data.ack.status === "ok" ||
      data.ack.status === "partial" ||
      data.ack.status === "error" ||
      data.ack.status === "rejected_stale" ||
      data.ack.status === "rejected_protocol"
    ) {
      state.mutating = false;
      state.optimisticSpeakerId = null;
    }
    if (data.ack.status === "rejected_protocol") {
      status.textContent =
        data.ack.message || "Protocol mismatch — reload or use classic UI.";
    }
  }

  const nameInput = qs<HTMLInputElement>(root, ".tx-sid-name-input");
  if (document.activeElement !== nameInput) {
    nameInput.value = data.draft_name || "";
  }
  const link = qs<HTMLInputElement>(root, ".tx-sid-link-profile");
  link.disabled = !(data.link_profile_allowed ?? data.capabilities?.profile_link);
  const disabled = Boolean(data.ui?.disabled || state.mutating);
  for (const sel of [".tx-sid-save", ".tx-sid-ignore", ".tx-sid-prev", ".tx-sid-next"]) {
    qs<HTMLButtonElement>(root, sel).disabled = disabled;
  }

  renderSpeakers(root, data, state);
  renderSamples(root, data, state);
  state.lastDataRef = data;
}

function wireOnce(
  host: HostElement,
  root: Element,
  args: FrontendRendererArgs<WorkspaceState, WorkspaceData>,
): InstanceState {
  const audio = qs<HTMLAudioElement>(root, ".tx-sid-audio");
  const state: InstanceState = {
    wired: true,
    audio,
    blobUrls: new Map(),
    blobBytes: 0,
    lastAckSeq: 0,
    actionSeq: 0,
    mutating: false,
    optimisticSpeakerId: null,
    retryTimers: [],
    handlers: {
      onSave: () => undefined,
      onIgnore: () => undefined,
      onPrev: () => undefined,
      onNext: () => undefined,
      onKey: () => undefined,
      onNameInput: () => undefined,
    },
    lastDataRef: null,
    setTriggerValue: args.setTriggerValue,
    setStateValue: args.setStateValue,
    host,
  };

  const refreshHandlers = () => {
    state.handlers.onSave = () => {
      const data = state.lastDataRef;
      if (!data) return;
      const name = qs<HTMLInputElement>(root, ".tx-sid-name-input").value.trim();
      const link = qs<HTMLInputElement>(root, ".tx-sid-link-profile").checked;
      fireCommand(
        state,
        data,
        "save_name",
        { display_name: name, link_profile: link },
        { mutating: true },
      );
    };
    state.handlers.onIgnore = () => {
      const data = state.lastDataRef;
      if (!data) return;
      fireCommand(state, data, "ignore_toggle", {}, { mutating: true });
    };
    state.handlers.onPrev = () => {
      const data = state.lastDataRef;
      if (!data) return;
      fireCommand(state, data, "navigate_prev");
    };
    state.handlers.onNext = () => {
      const data = state.lastDataRef;
      if (!data) return;
      fireCommand(state, data, "navigate_next");
    };
    state.handlers.onKey = (ev: KeyboardEvent) => {
      const target = ev.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      ) {
        return;
      }
      if (!root.contains(document.activeElement) && document.activeElement !== root) {
        const hostEl = state.host;
        const contains =
          "contains" in hostEl
            ? hostEl.contains(document.activeElement)
            : false;
        if (!contains) return;
      }
      const data = state.lastDataRef;
      if (!data) return;
      if (ev.key === "Enter") {
        ev.preventDefault();
        state.handlers.onSave();
      } else if (ev.key === " " || ev.code === "Space") {
        ev.preventDefault();
        if (state.audio.paused) void state.audio.play().catch(() => undefined);
        else state.audio.pause();
      } else if (ev.key === "j" || ev.key === "ArrowDown") {
        ev.preventDefault();
        state.handlers.onNext();
      } else if (ev.key === "k" || ev.key === "ArrowUp") {
        ev.preventDefault();
        state.handlers.onPrev();
      } else if (ev.key === "i") {
        ev.preventDefault();
        state.handlers.onIgnore();
      } else if (ev.key === "?") {
        const help = qs<HTMLElement>(root, ".tx-sid-help");
        help.hidden = !help.hidden;
        help.textContent =
          "Shortcuts (workspace focused): j/↓ next · k/↑ prev · Space play/pause · Enter save · i ignore · ? help";
      }
    };
  };
  refreshHandlers();

  qs<HTMLButtonElement>(root, ".tx-sid-save").addEventListener("click", () =>
    state.handlers.onSave(),
  );
  qs<HTMLButtonElement>(root, ".tx-sid-ignore").addEventListener("click", () =>
    state.handlers.onIgnore(),
  );
  qs<HTMLButtonElement>(root, ".tx-sid-prev").addEventListener("click", () =>
    state.handlers.onPrev(),
  );
  qs<HTMLButtonElement>(root, ".tx-sid-next").addEventListener("click", () =>
    state.handlers.onNext(),
  );
  const keyTarget: EventTarget =
    "addEventListener" in host ? host : (root as HTMLElement);
  keyTarget.addEventListener("keydown", (ev) =>
    state.handlers.onKey(ev as KeyboardEvent),
  );

  // Make root focusable for keyboard scope without stealing focus every render.
  const focusHost = (root.querySelector(".tx-sid-root") as HTMLElement | null) || (root as HTMLElement);
  if (!focusHost.hasAttribute("tabindex")) focusHost.setAttribute("tabindex", "0");

  return state;
}

const SpeakerIdWorkspace: FrontendRenderer<WorkspaceState, WorkspaceData> = (
  args,
) => {
  const { parentElement, data } = args;
  const host: HostElement = parentElement;
  const rootEl =
    (host as HTMLElement).querySelector?.(".tx-sid-root") ||
    (host as ShadowRoot).querySelector?.(".tx-sid-root") ||
    (host as unknown as Element);

  let state = instances.get(host);
  if (!state) {
    state = wireOnce(host, rootEl as Element, args);
    instances.set(host, state);
  } else {
    // Keep trigger/state setters fresh; never recreate audio.
    state.setTriggerValue = args.setTriggerValue;
    state.setStateValue = args.setStateValue;
  }

  applyData(rootEl as Element, data, state);

  return () => {
    const current = instances.get(host);
    if (!current) return;
    for (const t of current.retryTimers) window.clearTimeout(t);
    current.retryTimers = [];
    revokeAllBlobs(current);
    // Do not remove the audio element — parent unmount handles DOM.
    current.audio.removeAttribute("src");
    current.audio.load();
    instances.delete(host);
  };
};

export default SpeakerIdWorkspace;

/** Test helpers (Vitest). */
export const __test = {
  instances,
  ensureBlobUrl,
  revokeAllBlobs,
  PROTOCOL_VERSION,
  FRONTEND_BUILD_ID,
};
