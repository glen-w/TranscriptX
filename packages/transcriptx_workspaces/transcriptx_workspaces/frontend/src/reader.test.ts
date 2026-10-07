import { describe, expect, it } from "vitest";

import { __test, pickActiveHighlight, type ReaderSegment } from "./reader";

describe("reader highlight", () => {
  const segments: ReaderSegment[] = [
    {
      index: 0,
      speaker: "A",
      text: "hello world",
      start: 0,
      end: 2,
      mode: "karaoke",
      words: [
        { t: "hello", t0: 0, t1: 1 },
        { t: "world", t0: 1, t1: 2 },
      ],
    },
    {
      index: 1,
      speaker: "B",
      text: "segment only",
      start: 2,
      end: 4,
      mode: "segment",
      words: [{ t: "segment" }, { t: "only" }],
    },
  ];

  it("highlights timed word", () => {
    expect(pickActiveHighlight(segments, 0.5)).toEqual({
      segmentIndex: 0,
      wordIndex: 0,
    });
  });

  it("highlights segment mode without word index", () => {
    expect(pickActiveHighlight(segments, 2.5)).toEqual({
      segmentIndex: 1,
      wordIndex: null,
    });
  });

  it("does not match word without t0", () => {
    const segOnly: ReaderSegment[] = [
      {
        index: 0,
        speaker: "A",
        text: "x",
        start: 0,
        end: 1,
        mode: "karaoke",
        words: [{ t: "x" }],
      },
    ];
    expect(pickActiveHighlight(segOnly, 0.2).wordIndex).toBeNull();
  });
});

describe("audio src stability", () => {
  it("does not change key when only search_text differs", () => {
    const state = { lastSrcKey: "http://127.0.0.1:1/audio/t\x001:2" };
    const base = {
      audio_url: "http://127.0.0.1:1/audio/t",
      audio_fingerprint: "1:2",
    };
    const a = __test.applyAudioSrcKey(state, {
      ...base,
      search_text: "foo",
    } as never);
    const b = __test.applyAudioSrcKey(state, {
      ...base,
      search_text: "bar",
    } as never);
    expect(a.key).toBe(b.key);
    expect(a.changed).toBe(false);
  });
});
