/**
 * Theme D transcript reader (CCv2): full-file loopback audio + karaoke list.
 * Playhead stays browser-local — never stream current_time to Python.
 */

import type { FrontendRenderer } from "@streamlit/component-v2-lib";

import { FRONTEND_BUILD_ID, PROTOCOL_VERSION } from "./constants";

export type ReaderWord = {
  t: string;
  t0?: number;
  t1?: number;
};

export type ReaderSegment = {
  index: number;
  speaker: string;
  text: string;
  start: number;
  end: number;
  mode: "karaoke" | "segment";
  words: ReaderWord[];
  named?: boolean;
};

export type ReaderData = {
  protocol_version: string;
  frontend_build_id: string;
  transcript_id: string;
  transcript_revision: string;
  audio_url: string | null;
  audio_fingerprint: string | null;
  audio_ready: boolean;
  unavailable_reason: string | null;
  search_text: string;
  show_unnamed: boolean;
  jump_epoch: number;
  jump_index: number | null;
  autoplay_jump: boolean;
  segments: ReaderSegment[];
  word_timing_omitted?: boolean;
};

type InstanceState = {
  wired: boolean;
  audio: HTMLAudioElement;
  lastSrcKey: string | null;
  lastJumpEpoch: number;
  lastActiveIndex: number | null;
  segmentEls: Map<number, HTMLElement>;
};

const instances = new WeakMap<object, InstanceState>();

function qs<T extends Element>(root: ParentNode, sel: string): T {
  const el = root.querySelector(sel);
  if (!el) throw new Error(`Missing element: ${sel}`);
  return el as T;
}

export function pickActiveHighlight(
  segments: ReaderSegment[],
  timeSec: number,
): { segmentIndex: number | null; wordIndex: number | null } {
  let segmentIndex: number | null = null;
  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i];
    const isLast = i === segments.length - 1;
    const inRange =
      timeSec >= seg.start && (isLast ? timeSec <= seg.end : timeSec < seg.end);
    if (inRange) {
      segmentIndex = seg.index;
      if (seg.mode !== "karaoke") {
        return { segmentIndex, wordIndex: null };
      }
      for (let wi = 0; wi < seg.words.length; wi++) {
        const w = seg.words[wi];
        if (w.t0 != null && w.t1 != null && timeSec >= w.t0 && timeSec < w.t1) {
          return { segmentIndex, wordIndex: wi };
        }
      }
      return { segmentIndex, wordIndex: null };
    }
  }
  return { segmentIndex, wordIndex: null };
}

function segmentVisible(seg: ReaderSegment, data: ReaderData): boolean {
  if (!data.show_unnamed && seg.named === false) {
    return false;
  }
  const q = (data.search_text || "").trim().toLowerCase();
  if (!q) return true;
  const hay = `${seg.speaker} ${seg.text}`.toLowerCase();
  return hay.includes(q);
}

function windowBounds(
  segments: ReaderSegment[],
  centerIndex: number | null,
): { start: number; end: number } {
  if (segments.length <= 300) {
    return { start: 0, end: segments.length };
  }
  const center =
    centerIndex != null
      ? segments.findIndex((s) => s.index === centerIndex)
      : 0;
  const c = center >= 0 ? center : 0;
  const half = 40;
  const start = Math.max(0, c - half);
  const end = Math.min(segments.length, start + 80);
  return { start, end };
}

function applyAudioSrc(
  state: InstanceState,
  data: ReaderData,
  root: Element,
): void {
  const cap = qs<HTMLElement>(root, ".tx-reader-caption");
  if (
    data.protocol_version !== PROTOCOL_VERSION ||
    data.frontend_build_id !== FRONTEND_BUILD_ID
  ) {
    cap.textContent = "Reader workspace build mismatch — reload the page.";
    return;
  }
  if (!data.audio_ready || !data.audio_url) {
    cap.textContent =
      data.unavailable_reason === "no_audio"
        ? "No audio file for this transcript."
        : data.unavailable_reason === "media_route_off"
          ? "Full-file playback requires loopback host (127.0.0.1)."
          : "Playback unavailable.";
    return;
  }
  const key = `${data.audio_url}\0${data.audio_fingerprint ?? ""}`;
  if (state.lastSrcKey !== key) {
    state.audio.src = data.audio_url;
    state.lastSrcKey = key;
  }
  if (data.word_timing_omitted) {
    cap.textContent =
      "Word highlight omitted — transcript payload too large. Segment highlight only.";
  } else if (data.segments.some((s) => s.mode === "karaoke")) {
    cap.textContent = "Click a timed word to seek. Playhead stays in the player.";
  } else {
    cap.textContent =
      "Word timings missing or incomplete — highlighting the whole segment (no invented timings).";
  }
}

function paintHighlight(
  state: InstanceState,
  data: ReaderData,
  timeSec: number,
  root: Element,
): void {
  const { segmentIndex, wordIndex } = pickActiveHighlight(data.segments, timeSec);
  state.segmentEls.forEach((el, idx) => {
    const active = segmentIndex !== null && idx === segmentIndex;
    el.classList.toggle("tx-reader-turn--active", active);
    const words = el.querySelectorAll<HTMLElement>(".tx-reader-word");
    words.forEach((wEl, wi) => {
      wEl.classList.remove("tx-reader-word--active", "tx-reader-word--spoken");
      if (!active) return;
      if (data.segments.find((s) => s.index === idx)?.mode !== "karaoke") {
        return;
      }
      if (wordIndex !== null && wi === wordIndex) {
        wEl.classList.add("tx-reader-word--active");
      } else if (wordIndex !== null && wi < wordIndex) {
        wEl.classList.add("tx-reader-word--spoken");
      }
    });
  });

  if (segmentIndex !== null && segmentIndex !== state.lastActiveIndex) {
    state.lastActiveIndex = segmentIndex;
    const el = state.segmentEls.get(segmentIndex);
    const scroll = qs<HTMLElement>(root, ".tx-reader-scroll");
    if (el && scroll) {
      const top = el.offsetTop;
      const bottom = top + el.offsetHeight;
      if (top < scroll.scrollTop || bottom > scroll.scrollTop + scroll.clientHeight) {
        el.scrollIntoView({ block: "nearest" });
      }
    }
  }
}

function renderSegments(state: InstanceState, data: ReaderData, root: Element): void {
  const scroll = qs<HTMLElement>(root, ".tx-reader-scroll");
  const status = qs<HTMLElement>(root, ".tx-reader-status");
  const center =
    data.jump_index ?? state.lastActiveIndex ?? data.segments[0]?.index ?? null;
  const { start, end } = windowBounds(data.segments, center);
  scroll.replaceChildren();
  state.segmentEls.clear();

  if (data.segments.length > 300) {
    status.textContent = `Showing turns ${start + 1}–${end} of ${data.segments.length}`;
  } else {
    status.textContent = "";
  }

  for (let i = start; i < end; i++) {
    const seg = data.segments[i];
    const turn = document.createElement("div");
    turn.className = "tx-reader-turn";
    turn.dataset.index = String(seg.index);
    if (!segmentVisible(seg, data)) {
      turn.classList.add("tx-reader-hidden");
    }

    const head = document.createElement("div");
    head.className = "tx-reader-turn-head";
    head.textContent = `${seg.speaker} · ${seg.start.toFixed(1)}s`;
    turn.appendChild(head);

    const body = document.createElement("div");
    body.className = "tx-reader-turn-body";
    if (seg.mode === "karaoke" && seg.words.length) {
      seg.words.forEach((w, wi) => {
        const span = document.createElement("span");
        span.className = "tx-reader-word";
        span.textContent = w.t;
        if (w.t0 != null) {
          span.addEventListener("click", () => {
            state.audio.currentTime = w.t0 as number;
            void state.audio.play().catch(() => undefined);
          });
        } else {
          span.addEventListener("click", () => {
            state.audio.currentTime = seg.start;
          });
        }
        body.appendChild(span);
        if (wi < seg.words.length - 1) {
          body.appendChild(document.createTextNode(" "));
        }
      });
    } else {
      body.textContent = seg.text;
      body.addEventListener("click", () => {
        state.audio.currentTime = seg.start;
        void state.audio.play().catch(() => undefined);
      });
    }
    turn.appendChild(body);
    scroll.appendChild(turn);
    state.segmentEls.set(seg.index, turn);
  }
}

function handleJump(state: InstanceState, data: ReaderData, root: Element): void {
  if (data.jump_epoch === state.lastJumpEpoch) return;
  state.lastJumpEpoch = data.jump_epoch;
  const idx = data.jump_index;
  if (idx == null) return;
  const seg = data.segments.find((s) => s.index === idx);
  if (!seg) return;
  const el = state.segmentEls.get(idx);
  if (el) {
    el.scrollIntoView({ block: "center" });
  }
  if (data.autoplay_jump) {
    state.audio.currentTime = seg.start;
    void state.audio.play().catch(() => undefined);
  }
}

function wireKeyboard(state: InstanceState, root: Element): void {
  root.addEventListener("keydown", (ev) => {
    const kev = ev as KeyboardEvent;
    const t = kev.target as HTMLElement;
    if (t.tagName === "INPUT" || t.tagName === "TEXTAREA") return;
    const data = (root as HTMLElement & { __txReaderData?: ReaderData }).__txReaderData;
    if (!data) return;
    if (kev.code === "Space") {
      kev.preventDefault();
      if (state.audio.paused) void state.audio.play().catch(() => undefined);
      else state.audio.pause();
    }
    if (kev.key === "j" || kev.key === "ArrowDown") {
      const cur = state.audio.currentTime;
      const next = data.segments.find((s) => s.start > cur + 0.05);
      if (next) {
        state.audio.currentTime = next.start;
      }
    }
    if (kev.key === "k" || kev.key === "ArrowUp") {
      const cur = state.audio.currentTime;
      let prev: ReaderSegment | null = null;
      for (const s of data.segments) {
        if (s.start < cur - 0.05) prev = s;
      }
      if (prev) state.audio.currentTime = prev.start;
    }
  });
}

function wireOnce(root: Element, audio: HTMLAudioElement): InstanceState {
  const state: InstanceState = {
    wired: true,
    audio,
    lastSrcKey: null,
    lastJumpEpoch: -1,
    lastActiveIndex: null,
    segmentEls: new Map(),
  };
  audio.addEventListener("timeupdate", () => {
    const data = (root as HTMLElement & { __txReaderData?: ReaderData }).__txReaderData;
    if (data) paintHighlight(state, data, audio.currentTime, root);
  });
  return state;
}

const ReaderWorkspace: FrontendRenderer<Record<string, never>, ReaderData> = (
  args,
) => {
  const { parentElement, data } = args;
  const host = parentElement;
  const rootEl =
    (host as HTMLElement).querySelector?.(".tx-reader-root") ||
    (host as unknown as Element);

  let inst = instances.get(host);
  if (!inst) {
    const audio = qs<HTMLAudioElement>(rootEl as Element, ".tx-reader-audio");
    inst = wireOnce(rootEl as Element, audio);
    instances.set(host, inst);
    wireKeyboard(inst, rootEl as Element);
  }

  (rootEl as HTMLElement & { __txReaderData?: ReaderData }).__txReaderData = data;
  applyAudioSrc(inst, data, rootEl as Element);
  renderSegments(inst, data, rootEl as Element);
  handleJump(inst, data, rootEl as Element);
  paintHighlight(inst, data, inst.audio.currentTime, rootEl as Element);

  return () => {
    instances.delete(host);
  };
};

export const __test = {
  FRONTEND_BUILD_ID,
  pickActiveHighlight,
  applyAudioSrcKey: (state: { lastSrcKey: string | null }, data: ReaderData) => {
    const key = `${data.audio_url ?? ""}\0${data.audio_fingerprint ?? ""}`;
    return { key, changed: state.lastSrcKey !== key };
  },
};

export default ReaderWorkspace;
