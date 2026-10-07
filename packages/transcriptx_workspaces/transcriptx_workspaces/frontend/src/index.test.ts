import { describe, expect, it } from "vitest";
import { __test } from "./index";

describe("Speaker ID workspace lifecycle helpers", () => {
  it("exports stable protocol/build ids", () => {
    expect(__test.PROTOCOL_VERSION).toBe("1");
    expect(__test.FRONTEND_BUILD_ID).toBe("tx-workspaces-0.3.0");
  });

  it("ranks typed names ahead of the rest of the profile catalog", () => {
    const rows = [
      { mode: "existing", profile_id: "p-hugo", label: "Hugo", display_name: "Hugo" },
      { mode: "existing", profile_id: "p-ana", label: "Ana", display_name: "Ana" },
      { mode: "create", label: "Create new profile" },
      { mode: "none", label: "Name only — this transcript" },
    ];
    expect(__test.rankLinkRows(rows, "").map((row) => row.mode === "existing" ? row.profile_id : row.mode)).toEqual([
      "create",
      "none",
      "p-hugo",
      "p-ana",
    ]);
    expect(__test.rankLinkRows(rows, "Ana").map((row) => row.profile_id || row.mode)).toEqual([
      "p-ana",
      "create",
      "none",
      "p-hugo",
    ]);
  });

  it("fills the name input when a suggestion is picked", () => {
    document.body.innerHTML = `
      <input class="tx-sid-name-input" />
      <select class="tx-sid-name-pick"></select>
    `;
    const input = document.querySelector(".tx-sid-name-input") as HTMLInputElement;
    const pick = document.querySelector(".tx-sid-name-pick") as HTMLSelectElement;
    __test.applyNamePick(input, pick, { display_name: "Maya" });
    expect(input.value).toBe("Maya");
    expect(pick.value).toBe("Maya");
  });

  it("parses link target tokens for save_name", () => {
    expect(__test.parseLinkToken("none")).toEqual({
      link_mode: "none",
      profile_id: null,
      link_profile: false,
    });
    expect(__test.parseLinkToken("create")).toEqual({
      link_mode: "create",
      profile_id: null,
      link_profile: true,
    });
    expect(__test.parseLinkToken("existing:p-maya")).toEqual({
      link_mode: "existing",
      profile_id: "p-maya",
      link_profile: true,
    });
  });

  it("keeps expected speaker as the current active id", () => {
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

  it("async clip fulfill loads without autoplay and prompts ▶", () => {
    if (typeof URL === "undefined" || typeof URL.createObjectURL !== "function") {
      return;
    }
    const created: string[] = [];
    const origCreate = URL.createObjectURL.bind(URL);
    const origRevoke = URL.revokeObjectURL?.bind(URL);
    URL.createObjectURL = ((blob: Blob) => {
      const url = `blob:test-${created.length}`;
      created.push(url);
      return url;
    }) as typeof URL.createObjectURL;
    if (URL.revokeObjectURL) {
      URL.revokeObjectURL = (() => undefined) as typeof URL.revokeObjectURL;
    }
    try {
      document.body.innerHTML = `
        <div class="tx-sid-root">
          <audio class="tx-sid-audio"></audio>
          <div class="tx-sid-clip-status">Preparing clip…</div>
        </div>
      `;
      const root = document.querySelector(".tx-sid-root") as HTMLElement;
      const audio = root.querySelector("audio") as HTMLAudioElement;
      const playCalls: string[] = [];
      audio.play = (() => {
        playCalls.push("play");
        return Promise.resolve();
      }) as typeof audio.play;

      const state = {
        blobUrls: new Map<string, string>(),
        blobBytes: 0,
        audio,
      } as any;
      const sample = {
        clip_id: "c1",
        start: 0,
        end: 1,
        text: "hi",
        clip_b64: btoa("ID3fake"),
      };
      const ok = __test.playSampleBlob(state, root, sample, 1_000_000, {
        autoplay: false,
      });
      expect(ok).toBe(true);
      expect(playCalls).toEqual([]);
      expect(root.querySelector(".tx-sid-clip-status")?.textContent).toBe(
        "Ready — click ▶ to play",
      );
      expect(created.length).toBe(1);
      expect(audio.src).toContain("blob:test-0");
    } finally {
      URL.createObjectURL = origCreate;
      if (origRevoke && URL.revokeObjectURL) URL.revokeObjectURL = origRevoke;
    }
  });
});
