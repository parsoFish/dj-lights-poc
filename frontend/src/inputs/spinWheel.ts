import type { Bridge } from "../transport/bridge.js";

/**
 * Mouse-driven spin gesture: drag in a circle on the wheel canvas to emit
 * `spin` events with direction + RPM. Stand-in for a real DJ deck signal --
 * the engine only sees `Event(kind="spin")` either way.
 */
export class SpinWheel {
  private dragging = false;
  private lastAngle: number | null = null;
  private lastTimestamp = 0;
  private cumulativeRad = 0;
  private windowStart = 0;
  private rafHandle: number | null = null;

  constructor(
    private readonly canvas: HTMLCanvasElement,
    private readonly bridge: Bridge,
  ) {
    canvas.addEventListener("mousedown", this.onDown);
    canvas.addEventListener("mousemove", this.onMove);
    window.addEventListener("mouseup", this.onUp);
    this.draw(0);
  }

  destroy(): void {
    this.canvas.removeEventListener("mousedown", this.onDown);
    this.canvas.removeEventListener("mousemove", this.onMove);
    window.removeEventListener("mouseup", this.onUp);
    if (this.rafHandle !== null) cancelAnimationFrame(this.rafHandle);
  }

  private centre(): { x: number; y: number } {
    return { x: this.canvas.width / 2, y: this.canvas.height / 2 };
  }

  private angleAt(e: MouseEvent): number {
    const rect = this.canvas.getBoundingClientRect();
    const c = this.centre();
    const x = e.clientX - rect.left - c.x;
    const y = e.clientY - rect.top - c.y;
    return Math.atan2(y, x);
  }

  private onDown = (e: MouseEvent): void => {
    this.dragging = true;
    this.lastAngle = this.angleAt(e);
    this.lastTimestamp = performance.now();
    this.cumulativeRad = 0;
    this.windowStart = this.lastTimestamp;
  };

  private onMove = (e: MouseEvent): void => {
    if (!this.dragging || this.lastAngle === null) return;
    const now = performance.now();
    const angle = this.angleAt(e);
    let delta = angle - this.lastAngle;
    if (delta > Math.PI) delta -= 2 * Math.PI;
    if (delta < -Math.PI) delta += 2 * Math.PI;
    this.cumulativeRad += delta;
    this.lastAngle = angle;
    this.lastTimestamp = now;

    if (now - this.windowStart > 100) {
      const rps = this.cumulativeRad / (2 * Math.PI) / ((now - this.windowStart) / 1000);
      const rpm = Math.abs(rps) * 60;
      const direction = rps >= 0 ? "cw" : "ccw";
      if (rpm > 5) {
        this.bridge.send({
          kind: "spin",
          timestamp_ms: now,
          payload: { rpm, direction },
        });
      }
      this.windowStart = now;
      this.cumulativeRad = 0;
    }
    this.draw(angle);
  };

  private onUp = (): void => {
    this.dragging = false;
    this.lastAngle = null;
  };

  private draw(angle: number): void {
    const ctx = this.canvas.getContext("2d");
    if (!ctx) return;
    const c = this.centre();
    const r = Math.min(c.x, c.y) - 10;
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    ctx.strokeStyle = "rgba(255,255,255,0.3)";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(c.x, c.y, r, 0, Math.PI * 2);
    ctx.stroke();
    ctx.strokeStyle = "#39f";
    ctx.lineWidth = 5;
    ctx.beginPath();
    ctx.moveTo(c.x, c.y);
    ctx.lineTo(c.x + Math.cos(angle) * r, c.y + Math.sin(angle) * r);
    ctx.stroke();
  }
}
