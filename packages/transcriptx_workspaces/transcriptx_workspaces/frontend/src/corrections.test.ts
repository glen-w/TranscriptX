import { describe, expect, it } from "vitest";
import { __test } from "./corrections";

describe("Corrections workspace protocol ids", () => {
  it("matches shared build identity", () => {
    expect(__test.PROTOCOL_VERSION).toBe("1");
    expect(__test.FRONTEND_BUILD_ID).toBe("tx-workspaces-0.3.0");
  });

  it("suppresses shortcuts while the draft input is focused", () => {
    const input = document.createElement("input");
    const textarea = document.createElement("textarea");
    const div = document.createElement("div");
    expect(__test.isTypingTarget(input)).toBe(true);
    expect(__test.isTypingTarget(textarea)).toBe(true);
    expect(__test.isTypingTarget(div)).toBe(false);
    expect(__test.isTypingTarget(null)).toBe(false);
  });
});
