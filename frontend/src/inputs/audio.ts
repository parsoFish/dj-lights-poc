import type { Bridge } from "../transport/bridge.js";

/**
 * Energy-onset beat detector.
 *
 * Pipeline: getUserMedia -> AnalyserNode -> running average of frame energy.
 * If the current energy exceeds the average by `threshold` (and we're past
 * a refractory window), emit a `beat` event with a rolling BPM estimate.
 * Library-free; tuned for "loud kick at low frequencies" and good enough
 * to demo the trigger->effect->frame pipeline.
 *
 * Future agent: replace this with `aubio.js` or a backend-side detector for
 * tighter sync; the event payload contract stays the same.
 */
export interface BeatDetectorOptions {
  threshold: number;
  refractoryMs: number;
  windowMs: number;
  lowPassHz: number;
}

const DEFAULTS: BeatDetectorOptions = {
  threshold: 1.4,
  refractoryMs: 220,
  windowMs: 1500,
  lowPassHz: 200,
};

export class BeatDetector {
  private ctx: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private stream: MediaStream | null = null;
  private rafHandle: number | null = null;
  private lastBeatMs = 0;
  private recentBeats: number[] = [];
  private energyHistory: number[] = [];
  public bpm = 0;

  constructor(
    private readonly bridge: Bridge,
    private readonly opts: BeatDetectorOptions = DEFAULTS,
    public onBpm: (bpm: number) => void = () => {},
  ) {}

  async start(): Promise<void> {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.stream = stream;
    const ctx = new AudioContext();
    const source = ctx.createMediaStreamSource(stream);
    const filter = ctx.createBiquadFilter();
    filter.type = "lowpass";
    filter.frequency.value = this.opts.lowPassHz;
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 1024;
    source.connect(filter);
    filter.connect(analyser);
    this.ctx = ctx;
    this.analyser = analyser;
    this.tick();
  }

  stop(): void {
    if (this.rafHandle !== null) cancelAnimationFrame(this.rafHandle);
    this.rafHandle = null;
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    this.ctx?.close();
    this.ctx = null;
    this.analyser = null;
  }

  private tick = (): void => {
    if (!this.analyser) return;
    const buf = new Uint8Array(this.analyser.frequencyBinCount);
    this.analyser.getByteTimeDomainData(buf);
    let sum = 0;
    for (let i = 0; i < buf.length; i++) {
      const v = (buf[i]! - 128) / 128;
      sum += v * v;
    }
    const energy = Math.sqrt(sum / buf.length);
    this.energyHistory.push(energy);
    const cutoff = performance.now() - this.opts.windowMs;
    while (
      this.energyHistory.length > 30 &&
      this.energyHistory[0] !== undefined &&
      this.energyHistory.length * (this.opts.windowMs / 30) > 2 * (performance.now() - cutoff)
    ) {
      this.energyHistory.shift();
    }
    const avg =
      this.energyHistory.reduce((a, b) => a + b, 0) / Math.max(1, this.energyHistory.length);

    const now = performance.now();
    if (
      energy > avg * this.opts.threshold &&
      now - this.lastBeatMs > this.opts.refractoryMs &&
      avg > 0.005
    ) {
      this.lastBeatMs = now;
      this.recentBeats.push(now);
      this.recentBeats = this.recentBeats.filter((t) => now - t < 4000);
      const bpm = this.estimateBpm();
      this.bpm = bpm;
      this.onBpm(bpm);
      this.bridge.send({
        kind: "beat",
        timestamp_ms: now,
        payload: { bpm, confidence: Math.min(1, energy / Math.max(avg, 0.001) - 1) },
      });
    }
    this.rafHandle = requestAnimationFrame(this.tick);
  };

  private estimateBpm(): number {
    if (this.recentBeats.length < 2) return 0;
    const intervals: number[] = [];
    for (let i = 1; i < this.recentBeats.length; i++) {
      const a = this.recentBeats[i - 1]!;
      const b = this.recentBeats[i]!;
      intervals.push(b - a);
    }
    intervals.sort((a, b) => a - b);
    const median = intervals[Math.floor(intervals.length / 2)]!;
    return Math.round(60000 / median);
  }
}
