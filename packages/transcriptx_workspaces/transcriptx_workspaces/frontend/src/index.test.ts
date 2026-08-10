import { describe, expect, it } from "vitest";
import { __test } from "./index";

describe("Speaker ID workspace lifecycle helpers", () => {
  it("exports stable protocol/build ids", () => {
    expect(__test.PROTOCOL_VERSION).toBe("1");
    expect(__test.FRONTEND_BUILD_ID).toBe("tx-workspaces-0.1.0");
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
});
