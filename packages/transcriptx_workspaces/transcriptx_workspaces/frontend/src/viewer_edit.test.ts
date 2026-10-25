/**
 * Transcript Correct-mode word-span selection (viewer_edit.ts).
 *
 * Host markup mirrors _VIEWER_EDIT_HTML in transcriptx_workspaces/__init__.py.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ViewerEditWorkspace, {
  type ViewerEditData,
  type ViewerSelection,
} from "./viewer_edit";

const HOST_HTML = `
  <div class="tx-vedit-root" data-testid="viewer-edit-workspace" tabindex="0">
    <div class="tx-vedit-words"></div>
    <p class="tx-vedit-caption"></p>
  </div>
`;

const DATA: ViewerEditData = {
  segment_id: "seg-1",
  words: [
    { i: 0, text: "the" },
    { i: 1, text: "quick", low_conf: true },
    { i: 2, text: "brown" },
    { i: 3, text: "fox" },
  ],
};

type SetState = (key: string, value: ViewerSelection) => void;

function render(host: HTMLElement, data: ViewerEditData, setStateValue: SetState) {
  // Only the fields viewer_edit reads; the real args object has more.
  const args = { parentElement: host, data, setStateValue } as unknown as Parameters<
    typeof ViewerEditWorkspace
  >[0];
  return ViewerEditWorkspace(args) as () => void;
}

function words(host: HTMLElement): HTMLElement[] {
  return Array.from(host.querySelectorAll<HTMLElement>(".tx-vedit-word"));
}

function selected(host: HTMLElement): string[] {
  return words(host)
    .filter((el) => el.getAttribute("aria-selected") === "true")
    .map((el) => el.textContent ?? "");
}

function caption(host: HTMLElement): string {
  return host.querySelector(".tx-vedit-caption")?.textContent ?? "";
}

describe("viewer_edit word-span selection", () => {
  let host: HTMLElement;
  let setStateValue: ReturnType<typeof vi.fn<SetState>>;
  let cleanup: (() => void) | undefined;

  beforeEach(() => {
    document.body.innerHTML = `<div class="host">${HOST_HTML}</div>`;
    host = document.querySelector<HTMLElement>(".host")!;
    setStateValue = vi.fn<SetState>();
    cleanup = render(host, DATA, setStateValue);
  });

  afterEach(() => {
    cleanup?.();
    window.dispatchEvent(new MouseEvent("mouseup"));
  });

  it("renders one span per word and marks low-confidence words", () => {
    expect(words(host).map((el) => el.textContent)).toEqual([
      "the",
      "quick",
      "brown",
      "fox",
    ]);
    expect(words(host)[1].classList.contains("tx-vedit-low")).toBe(true);
    expect(words(host)[0].classList.contains("tx-vedit-low")).toBe(false);
    expect(caption(host)).toBe("Click and drag to select a word span.");
  });

  it("selects a single word on mousedown and reports it to Streamlit", () => {
    words(host)[2].dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    expect(setStateValue).toHaveBeenLastCalledWith("selection", {
      i0: 2,
      i1: 2,
      text: "brown",
    });
    expect(selected(host)).toEqual(["brown"]);
    expect(caption(host)).toBe("Selected: brown");
  });

  it("extends the span while dragging, in either direction", () => {
    const w = words(host);
    w[3].dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    w[1].dispatchEvent(new MouseEvent("mouseenter"));
    expect(setStateValue).toHaveBeenLastCalledWith("selection", {
      i0: 3,
      i1: 1,
      text: "quick brown fox",
    });
    expect(selected(host)).toEqual(["quick", "brown", "fox"]);
  });

  it("stops extending after mouseup", () => {
    const w = words(host);
    w[0].dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    window.dispatchEvent(new MouseEvent("mouseup"));
    setStateValue.mockClear();
    w[3].dispatchEvent(new MouseEvent("mouseenter"));
    expect(setStateValue).not.toHaveBeenCalled();
    expect(selected(host)).toEqual(["the"]);
  });

  it("keeps the selection painted across a re-render with new args", () => {
    words(host)[1].dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    window.dispatchEvent(new MouseEvent("mouseup"));
    const nextSet = vi.fn<SetState>();
    render(host, DATA, nextSet);
    expect(selected(host)).toEqual(["quick"]);
    words(host)[3].dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    expect(nextSet).toHaveBeenCalledWith("selection", { i0: 3, i1: 3, text: "fox" });
    expect(setStateValue).toHaveBeenCalledTimes(1);
  });

  it("starts fresh after cleanup", () => {
    words(host)[1].dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    cleanup?.();
    cleanup = render(host, DATA, setStateValue);
    expect(selected(host)).toEqual([]);
    expect(caption(host)).toBe("Click and drag to select a word span.");
  });
});
