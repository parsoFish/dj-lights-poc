import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TapTempo } from "../src/inputs/tapTempo.js";
import type { Bridge } from "../src/transport/bridge.js";

class FakeBridge {
  sent: Array<{ kind: string; payload: Record<string, unknown> }> = [];
  send(event: { kind: string; payload: Record<string, unknown> }): void {
    this.sent.push(event);
  }
}

describe("TapTempo", () => {
  let now = 0;
  beforeEach(() => {
    now = 0;
    vi.spyOn(performance, "now").mockImplementation(() => now);
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("estimates BPM from tap intervals", () => {
    const bridge = new FakeBridge() as unknown as Bridge;
    const reported: number[] = [];
    const tap = new TapTempo(bridge, { onBpm: (bpm) => reported.push(bpm) });
    // 500 ms between taps -> 120 BPM
    tap.tap();
    now = 500;
    tap.tap();
    now = 1000;
    tap.tap();
    expect(reported.at(-1)).toBe(120);
  });

  it("first tap reports 0 BPM", () => {
    const bridge = new FakeBridge() as unknown as Bridge;
    const reported: number[] = [];
    const tap = new TapTempo(bridge, { onBpm: (bpm) => reported.push(bpm) });
    tap.tap();
    expect(reported).toEqual([0]);
  });

  it("emits beat events on every tap", () => {
    const bridge = new FakeBridge();
    const tap = new TapTempo(bridge as unknown as Bridge);
    tap.tap();
    now = 600;
    tap.tap();
    expect(bridge.sent).toHaveLength(2);
    expect(bridge.sent[0]!.kind).toBe("beat");
    expect(bridge.sent[1]!.payload.bpm).toBe(100);
  });

  it("auto-loop ticks at the locked BPM", () => {
    vi.useFakeTimers();
    try {
      const bridge = new FakeBridge();
      const tap = new TapTempo(bridge as unknown as Bridge);
      tap.tap();
      now = 500;
      tap.tap(); // 120 BPM, interval 500 ms
      bridge.sent = [];
      tap.startAuto();
      vi.advanceTimersByTime(1500);
      const autoBeats = bridge.sent.filter((e) => e.payload.source === "auto");
      expect(autoBeats.length).toBe(3);
      tap.stopAuto();
    } finally {
      vi.useRealTimers();
    }
  });

  it("startAuto is a no-op until BPM is established", () => {
    vi.useFakeTimers();
    try {
      const bridge = new FakeBridge();
      const tap = new TapTempo(bridge as unknown as Bridge);
      tap.startAuto();
      expect(tap.autoRunning).toBe(false);
      vi.advanceTimersByTime(2000);
      expect(bridge.sent).toHaveLength(0);
    } finally {
      vi.useRealTimers();
    }
  });

  it("reset clears BPM and stops the auto-loop", () => {
    vi.useFakeTimers();
    try {
      const bridge = new FakeBridge();
      const tap = new TapTempo(bridge as unknown as Bridge);
      tap.tap();
      now = 500;
      tap.tap();
      tap.startAuto();
      tap.reset();
      expect(tap.autoRunning).toBe(false);
      expect(tap.bpm).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });
});
