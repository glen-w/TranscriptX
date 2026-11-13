import { describe, expect, it } from "vitest";
import {
  elementHasFocus,
  isTypingTarget,
  resolveActiveElement,
} from "./dom";

describe("dom focus helpers", () => {
  it("resolves focus inside an open shadow root", () => {
    const host = document.createElement("div");
    const root = host.attachShadow({ mode: "open" });
    const input = document.createElement("input");
    root.appendChild(input);
    document.body.appendChild(host);
    input.focus();
    expect(document.activeElement).toBe(host);
    expect(resolveActiveElement()).toBe(input);
    expect(elementHasFocus(input)).toBe(true);
    host.remove();
  });

  it("classifies typing targets", () => {
    expect(isTypingTarget(document.createElement("input"))).toBe(true);
    expect(isTypingTarget(document.createElement("textarea"))).toBe(true);
    expect(isTypingTarget(document.createElement("select"))).toBe(true);
    expect(isTypingTarget(document.createElement("div"))).toBe(false);
  });
});
