import { describe, expect, it } from "vitest";
import { __test } from "./index";

describe("Speaker ID workspace lifecycle helpers", () => {
  it("exports stable protocol/build ids", () => {
    expect(__test.PROTOCOL_VERSION).toBe("1");
    expect(__test.FRONTEND_BUILD_ID).toBe("tx-workspaces-0.1.0");
  });

  it("uses authoritative active speaker for stale checks, not optimistic target", () => {
    const data = {
      active_speaker_id: "SPEAKER_00",
    } as any;
    // Clicking SPEAKER_01 sets optimistic target before fireCommand; expected
    // must remain SPEAKER_00 so navigate_jump is not rejected_stale.
    expect(__test.expectedSpeakerForCommand(data, "SPEAKER_01")).toBe(
      "SPEAKER_00",
    );
  });

  it("rejects clips exceeding blob budget", () => {
    const state = {
      blobUrls: new Map<string, string>(),
      blobBytes: 0,
    } as any;
    const b64 = btoa("hello-audio");
    const url = __test.ensureBlobUrl(state, "c1", b64, 4);
    expect(url).toBeNull();
  });

  it("stores blob urls when createObjectURL is available", () => {
    const state = {
      blobUrls: new Map<string, string>(),
      blobBytes: 0,
    } as any;
    const b64 = btoa("hello-audio");
    const url = __test.ensureBlobUrl(state, "c1", b64, 1000);
    if (typeof URL === "undefined" || typeof URL.createObjectURL !== "function") {
      expect(url).toBeNull();
      return;
    }
    // jsdom may return opaque objects; presence in the map is the contract.
    if (url) {
      expect(state.blobUrls.get("c1")).toBeTruthy();
      __test.revokeAllBlobs(state);
      expect(state.blobUrls.size).toBe(0);
      expect(state.blobBytes).toBe(0);
    }
  });

  it("findPlayableSample matches by start/end when clip_id changes", () => {
    const data = {
      samples: [
        { clip_id: "hash-1", start: 1.0, end: 2.0, text: "a", clip_b64: "xx" },
      ],
    } as any;
    const found = __test.findPlayableSample(data, {
      clipId: "0.000-1.000",
      start: 1.0,
      end: 2.0,
      attempt: 1,
    });
    expect(found?.clip_id).toBe("hash-1");
    expect(
      __test.findPlayableSample(data, {
        clipId: "missing",
        start: 9,
        end: 10,
        attempt: 0,
      }),
    ).toBeUndefined();
  });
});
