import type { LedFrame, StageLayout } from "../types.js";

/**
 * "Strip" preview: each bar rendered horizontally with its segments side-by-side.
 * Independent of physical layout; useful for verifying frame data at a glance.
 */
export class StagePreview {
  constructor(
    private readonly canvas: HTMLCanvasElement,
    private layout: StageLayout,
  ) {
    this.draw(null);
  }

  setLayout(layout: StageLayout): void {
    this.layout = layout;
  }

  draw(frame: LedFrame | null): void {
    const ctx = this.canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    const barCount = this.layout.bars.length;
    if (barCount === 0) return;
    const padding = 12;
    const labelHeight = 14;
    const stripHeight = (this.canvas.height - padding * 2 - barCount * labelHeight) / barCount;
    let y = padding;
    for (const bar of this.layout.bars) {
      ctx.fillStyle = "rgba(255,255,255,0.7)";
      ctx.font = "11px sans-serif";
      ctx.fillText(bar.id, padding, y + 10);
      y += labelHeight;
      const segWidth = (this.canvas.width - padding * 2) / bar.segments;
      const barFrame = frame?.bars.find((b) => b.barId === bar.id);
      for (let i = 0; i < bar.segments; i++) {
        const px = barFrame?.pixels[i] ?? [20, 20, 20];
        ctx.fillStyle = `rgb(${px[0]},${px[1]},${px[2]})`;
        ctx.fillRect(padding + i * segWidth, y, Math.max(1, segWidth - 1), stripHeight);
      }
      y += stripHeight + 4;
    }
  }
}
