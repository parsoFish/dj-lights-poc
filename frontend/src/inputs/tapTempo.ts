import type { Bridge } from "../transport/bridge.js";

/**
 * Manual taps emit ``beat`` events with a rolling BPM estimate so the
 * beat-pulse demo is reachable without a microphone. Once at least two taps
 * have set a BPM, calling :meth:`startAuto` keeps the beat going at that
 * tempo until :meth:`stopAuto` (or :meth:`reset`).
 *
 * The auto-loop emits the same ``beat`` payload as the manual taps, so the
 * engine can't tell the difference.
 */
export interface TapTempoCallbacks {
  onBpm?: (bpm: number) => void;
  onAutoChange?: (running: boolean) => void;
}

export class TapTempo {
  private taps: number[] = [];
  private timer: ReturnType<typeof setInterval> | null = null;
  public bpm = 0;

  constructor(
    private readonly bridge: Bridge,
    private readonly cbs: TapTempoCallbacks = {},
  ) {}

  get autoRunning(): boolean {
    return this.timer !== null;
  }

  tap(): void {
    const now = performance.now();
    this.taps.push(now);
    this.taps = this.taps.filter((t) => now - t < 4000);
    if (this.taps.length >= 2) {
      const intervals: number[] = [];
      for (let i = 1; i < this.taps.length; i++) {
        const prev = this.taps[i - 1];
        const cur = this.taps[i];
        if (prev !== undefined && cur !== undefined) intervals.push(cur - prev);
      }
      const avg = intervals.reduce((a, b) => a + b, 0) / intervals.length;
      this.bpm = Math.round(60_000 / avg);
    } else {
      this.bpm = 0;
    }
    this.cbs.onBpm?.(this.bpm);
    this.emitBeat(now, "tap");
    if (this.timer !== null) this.restartTimer();
  }

  startAuto(): void {
    if (this.bpm <= 0) return;
    this.restartTimer();
    this.cbs.onAutoChange?.(true);
  }

  stopAuto(): void {
    if (this.timer !== null) {
      clearInterval(this.timer);
      this.timer = null;
      this.cbs.onAutoChange?.(false);
    }
  }

  reset(): void {
    this.stopAuto();
    this.taps = [];
    this.bpm = 0;
    this.cbs.onBpm?.(0);
  }

  private restartTimer(): void {
    if (this.timer !== null) clearInterval(this.timer);
    if (this.bpm <= 0) return;
    const intervalMs = 60_000 / this.bpm;
    this.timer = setInterval(() => this.emitBeat(performance.now(), "auto"), intervalMs);
  }

  private emitBeat(now: number, source: "tap" | "auto"): void {
    this.bridge.send({
      kind: "beat",
      timestamp_ms: now,
      payload: { bpm: this.bpm, confidence: 1.0, source },
    });
  }
}
