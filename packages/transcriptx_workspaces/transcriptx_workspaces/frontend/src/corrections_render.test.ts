/**
 * Corrections Studio renderer: candidate list, command envelopes, the
 * one-mutation-in-flight guard, protocol mismatch and keyboard shortcuts.
 *
 * Host markup mirrors _CORRECTIONS_HTML in transcriptx_workspaces/__init__.py.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import CorrectionsWorkspace, {
  __test,
  type CorrectionsCommandEnvelope,
  type CorrectionsData,
} from "./corrections";

const HOST_HTML = `
  <div class="tx-corr-root" data-testid="corrections-workspace" tabindex="0">
    <aside class="tx-corr-list" aria-label="Candidates"></aside>
    <section class="tx-corr-detail">
      <div class="tx-corr-status" aria-live="polite"></div>
      <div class="tx-corr-kind"></div>
      <p class="tx-corr-wrong"></p>
      <label><span>Replacement</span>
        <input type="text" class="tx-corr-draft" autocomplete="off" /></label>
      <div class="tx-corr-actions">
        <button type="button" class="tx-corr-accept">Accept</button>
        <button type="button" class="tx-corr-reject">Reject</button>
        <button type="button" class="tx-corr-skip">Skip</button>
        <button type="button" class="tx-corr-save-draft">Save draft</button>
      </div>
    </section>
  </div>
`;

function data(overrides: Partial<CorrectionsData> = {}): CorrectionsData {
  return {
    protocol_version: __test.PROTOCOL_VERSION,
    frontend_build_id: __test.FRONTEND_BUILD_ID,
    session_id: "sess-1",
    session_revision: "srev-1",
    active_candidate_id: "c1",
    candidates: [
      {
        id: "c1",
        kind: "spelling",
        status: "pending",
        wrong_text: "teh",
        right_text: "the",
        confidence: 0.9,
        revision: "r1",
      },
      {
        id: "c2",
        kind: "name",
        status: "pending",
        wrong_text: "jon",
        right_text: "John",
        confidence: 0.6,
        revision: "r2",
        viewer: true,
      },
    ],
    active: {
      id: "c1",
      kind: "spelling",
      status: "pending",
      wrong_text: "teh",
      right_text: "the",
      revision: "r1",
    },
    ack: null,
    ui: { status: "2 pending" },
    ...overrides,
  };
}

type Trigger = (key: string, value: CorrectionsCommandEnvelope) => void;
type SetState = (key: string, value: number) => void;

describe("Corrections Studio renderer", () => {
  let host: HTMLElement;
  let trigger: ReturnType<typeof vi.fn<Trigger>>;
  let setState: ReturnType<typeof vi.fn<SetState>>;
  let cleanup: (() => void) | undefined;

  const $ = <T extends Element = HTMLElement>(sel: string) =>
    host.querySelector(sel) as T;
  const lastCommand = () =>
    trigger.mock.calls[trigger.mock.calls.length - 1][1] as CorrectionsCommandEnvelope;

  function render(d: CorrectionsData) {
    const args = {
      parentElement: host,
      data: d,
      setTriggerValue: trigger,
      setStateValue: setState,
    } as unknown as Parameters<typeof CorrectionsWorkspace>[0];
    cleanup = CorrectionsWorkspace(args) as () => void;
  }

  beforeEach(() => {
    document.body.innerHTML = `<div class="host">${HOST_HTML}</div>`;
    host = document.querySelector<HTMLElement>(".host")!;
    trigger = vi.fn<Trigger>();
    setState = vi.fn<SetState>();
  });

  afterEach(() => cleanup?.());

  it("lists candidates, marks the active one and prefills the draft", () => {
    render(data());
    const items = Array.from(host.querySelectorAll(".tx-corr-cand"));
    expect(items.map((b) => b.textContent)).toEqual([
      "spelling — teh → the",
      "[viewer] name — jon → John",
    ]);
    expect(items[0].getAttribute("aria-current")).toBe("true");
    expect(items[1].hasAttribute("aria-current")).toBe(false);
    expect($<HTMLInputElement>(".tx-corr-draft").value).toBe("the");
    expect($(".tx-corr-kind").textContent).toBe("spelling · pending");
    expect($(".tx-corr-status").textContent).toBe("2 pending");
    expect($<HTMLButtonElement>(".tx-corr-accept").disabled).toBe(false);
  });

  it("disables actions when no candidate is active", () => {
    render(data({ active: null, active_candidate_id: null }));
    expect($(".tx-corr-wrong").textContent).toBe("Select a candidate.");
    for (const sel of [".tx-corr-accept", ".tx-corr-reject", ".tx-corr-skip"]) {
      expect($<HTMLButtonElement>(sel).disabled).toBe(true);
    }
  });

  it("sends an accept envelope with the edited draft and expected revisions", () => {
    render(data());
    $<HTMLInputElement>(".tx-corr-draft").value = "thee";
    $<HTMLButtonElement>(".tx-corr-accept").click();
    const env = lastCommand();
    expect(trigger.mock.calls[0][0]).toBe("command");
    expect(env).toMatchObject({
      protocol_version: __test.PROTOCOL_VERSION,
      frontend_build_id: __test.FRONTEND_BUILD_ID,
      action: "accept",
      action_seq: 1,
      session_id: "sess-1",
      expected_session_revision: "srev-1",
      expected_candidate_revision: "r1",
      candidate_id: "c1",
      payload: { review_target_raw: "thee" },
    });
    expect(env.action_id).toMatch(/^[0-9a-z]+$/);
    expect(setState).toHaveBeenCalledWith("ack_seq", 1);
  });

  it("allows one mutation in flight until Streamlit acks it", () => {
    render(data());
    $<HTMLButtonElement>(".tx-corr-reject").click();
    $<HTMLButtonElement>(".tx-corr-skip").click();
    expect(trigger).toHaveBeenCalledTimes(1);
    expect(lastCommand().action).toBe("reject");

    render(data());
    expect($<HTMLButtonElement>(".tx-corr-accept").disabled).toBe(true);

    render(data({ ack: { action_id: "x", action_seq: 1, status: "applied" } }));
    expect($<HTMLButtonElement>(".tx-corr-accept").disabled).toBe(false);
    $<HTMLButtonElement>(".tx-corr-skip").click();
    expect(trigger).toHaveBeenCalledTimes(2);
    expect(lastCommand()).toMatchObject({ action: "skip", action_seq: 2 });
  });

  it("selecting a candidate is not a mutation", () => {
    render(data());
    const items = host.querySelectorAll<HTMLButtonElement>(".tx-corr-cand");
    items[1].click();
    items[0].click();
    expect(trigger).toHaveBeenCalledTimes(2);
    expect(lastCommand()).toMatchObject({
      action: "select_candidate",
      payload: { candidate_id: "c1" },
    });
  });

  it("save draft sends edit_draft with the draft text", () => {
    render(data());
    $<HTMLInputElement>(".tx-corr-draft").value = "THE";
    $<HTMLButtonElement>(".tx-corr-save-draft").click();
    expect(lastCommand()).toMatchObject({
      action: "edit_draft",
      payload: { right_text: "THE" },
    });
  });

  it("reports a protocol mismatch instead of the requested action", () => {
    render(data({ frontend_build_id: "tx-workspaces-0.0.1" }));
    $<HTMLButtonElement>(".tx-corr-accept").click();
    expect(lastCommand()).toMatchObject({
      action: "protocol_mismatch",
      payload: { got_protocol: __test.PROTOCOL_VERSION, got_build: "tx-workspaces-0.0.1" },
    });
  });

  it("shows the server message when an action was rejected for protocol", () => {
    render(
      data({
        ack: {
          action_id: "x",
          action_seq: 0,
          status: "rejected_protocol",
          message: "Reload the page.",
        },
      }),
    );
    expect($(".tx-corr-status").textContent).toBe("Reload the page.");
  });

  it("maps a/r/s shortcuts to actions but not while typing in the draft", () => {
    render(data());
    const root = $(".tx-corr-root");
    const draft = $<HTMLInputElement>(".tx-corr-draft");
    draft.dispatchEvent(new KeyboardEvent("keydown", { key: "r", bubbles: true }));
    expect(trigger).not.toHaveBeenCalled();

    root.dispatchEvent(new KeyboardEvent("keydown", { key: "a", bubbles: true }));
    expect(lastCommand().action).toBe("accept");
  });
});
