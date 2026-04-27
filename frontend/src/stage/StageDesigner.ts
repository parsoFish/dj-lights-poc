import type { Bar, LedFrame, Pose2D, StageLayout } from "../types.js";
import {
  Viewport,
  barEndpoints,
  hitTestBar,
  pixelFor,
  screenToStage,
  segmentCentre,
  stageToScreen,
} from "./geometry.js";

interface DragState {
  kind: "move" | "rotate";
  barId: string;
  startStage: { x: number; y: number };
  startPose: { x: number; y: number; rot: number };
}

export interface DesignerCallbacks {
  onLayoutChange: (layout: StageLayout) => void;
  onSelect: (barId: string | null) => void;
  /**
   * Called whenever the cursor moves over the stage in hand-mode. Coordinates
   * are normalised to pad space: x ∈ [0,1] left→right, y ∈ [0,1] top→bottom
   * (pad-top = stage-back, pad-bottom = audience side / front bars).
   */
  onHandMove?: (padX: number, padY: number) => void;
}

/**
 * 2D top-down stage editor + live LED preview.
 *
 * Two interaction modes:
 *
 * - Default — click bars to select, drag to move, shift+drag to rotate.
 * - Hand mode — drag anywhere on the canvas to emit ``hand_position`` events
 *   and a pad cursor renders where the spot is being aimed. Toggled via
 *   :meth:`setHandMode`. This replaces the earlier sidebar pad so you can
 *   sweep a virtual hand directly across the bars.
 */
export class StageDesigner {
  private layout: StageLayout;
  private frame: LedFrame | null = null;
  private selectedBarId: string | null = null;
  private drag: DragState | null = null;
  private rafHandle: number | null = null;
  private handMode = false;
  private handDragging = false;
  private handPadPos: { x: number; y: number } | null = null;

  constructor(
    private readonly canvas: HTMLCanvasElement,
    layout: StageLayout,
    private readonly cbs: DesignerCallbacks,
  ) {
    this.layout = layout;
    canvas.addEventListener("mousedown", this.onMouseDown);
    canvas.addEventListener("mousemove", this.onMouseMove);
    window.addEventListener("mouseup", this.onMouseUp);
    this.scheduleDraw();
  }

  destroy(): void {
    this.canvas.removeEventListener("mousedown", this.onMouseDown);
    this.canvas.removeEventListener("mousemove", this.onMouseMove);
    window.removeEventListener("mouseup", this.onMouseUp);
    if (this.rafHandle !== null) cancelAnimationFrame(this.rafHandle);
  }

  setLayout(layout: StageLayout): void {
    this.layout = layout;
    this.scheduleDraw();
  }

  setFrame(frame: LedFrame): void {
    this.frame = frame;
    this.scheduleDraw();
  }

  selectBar(id: string | null): void {
    this.selectedBarId = id;
    this.cbs.onSelect(id);
    this.scheduleDraw();
  }

  setHandMode(enabled: boolean): void {
    this.handMode = enabled;
    this.handDragging = false;
    if (!enabled) this.handPadPos = null;
    this.canvas.style.cursor = enabled ? "crosshair" : "";
    this.scheduleDraw();
  }

  isHandMode(): boolean {
    return this.handMode;
  }

  selectedBar(): Bar | null {
    if (!this.selectedBarId) return null;
    return this.layout.bars.find((b) => b.id === this.selectedBarId) ?? null;
  }

  addBar(bar: Bar): void {
    this.layout = { ...this.layout, bars: [...this.layout.bars, bar] };
    this.cbs.onLayoutChange(this.layout);
    this.selectBar(bar.id);
  }

  removeBar(id: string): void {
    this.layout = { ...this.layout, bars: this.layout.bars.filter((b) => b.id !== id) };
    if (this.selectedBarId === id) this.selectBar(null);
    this.cbs.onLayoutChange(this.layout);
    this.scheduleDraw();
  }

  updateSelectedBar(patch: Omit<Partial<Bar>, "pose"> & { pose?: Partial<Pose2D> }): void {
    if (!this.selectedBarId) return;
    this.layout = {
      ...this.layout,
      bars: this.layout.bars.map((b) =>
        b.id === this.selectedBarId
          ? {
              ...b,
              ...patch,
              pose: patch.pose ? { ...b.pose, ...patch.pose } : b.pose,
            }
          : b,
      ),
    };
    this.cbs.onLayoutChange(this.layout);
    this.scheduleDraw();
  }

  private viewport(): Viewport {
    const padding = 40;
    const ppm = Math.min(
      (this.canvas.width - padding * 2) / this.layout.width_m,
      (this.canvas.height - padding * 2) / this.layout.depth_m,
    );
    return { width: this.canvas.width, height: this.canvas.height, pixelsPerMetre: ppm };
  }

  private scheduleDraw(): void {
    if (this.rafHandle !== null) return;
    this.rafHandle = requestAnimationFrame(() => {
      this.rafHandle = null;
      this.draw();
    });
  }

  private draw(): void {
    const ctx = this.canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    const vp = this.viewport();
    // Stage outline.
    const tl = stageToScreen(
      { x: -this.layout.width_m / 2, y: this.layout.depth_m / 2 },
      vp,
    );
    const br = stageToScreen(
      { x: this.layout.width_m / 2, y: -this.layout.depth_m / 2 },
      vp,
    );
    ctx.strokeStyle = "rgba(255,255,255,0.3)";
    ctx.lineWidth = 1;
    ctx.strokeRect(tl.x, tl.y, br.x - tl.x, br.y - tl.y);

    // Bars.
    for (const bar of this.layout.bars) {
      const [a, b] = barEndpoints(bar);
      const sa = stageToScreen(a, vp);
      const sb = stageToScreen(b, vp);
      ctx.strokeStyle = bar.id === this.selectedBarId ? "#39f" : "rgba(255,255,255,0.4)";
      ctx.lineWidth = 14;
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(sa.x, sa.y);
      ctx.lineTo(sb.x, sb.y);
      ctx.stroke();

      // Lit segments overlay.
      for (let i = 0; i < bar.segments; i++) {
        const c = stageToScreen(segmentCentre(bar, i), vp);
        const px = this.frame ? pixelFor(this.frame, bar.id, i) : undefined;
        const colour = px ? `rgb(${px[0]},${px[1]},${px[2]})` : "rgb(20,20,20)";
        ctx.fillStyle = colour;
        ctx.beginPath();
        ctx.arc(c.x, c.y, 5, 0, Math.PI * 2);
        ctx.fill();
      }

      // ID label.
      ctx.fillStyle = "rgba(255,255,255,0.6)";
      ctx.font = "11px sans-serif";
      ctx.fillText(bar.id, sa.x + 6, sa.y - 10);
    }

    // Hand cursor (only when hand-mode is on and we have a position).
    if (this.handMode && this.handPadPos) {
      const stageX = (this.handPadPos.x - 0.5) * this.layout.width_m;
      const stageY = (0.5 - this.handPadPos.y) * this.layout.depth_m;
      const c = stageToScreen({ x: stageX, y: stageY }, vp);
      ctx.strokeStyle = "#fc3";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(c.x, c.y, 14, 0, Math.PI * 2);
      ctx.stroke();
      ctx.fillStyle = "rgba(255, 204, 51, 0.5)";
      ctx.beginPath();
      ctx.arc(c.x, c.y, 5, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  private mouseToCanvas(e: MouseEvent): { x: number; y: number } {
    // CSS-pixel mouse coords need to map to the canvas's internal pixel space.
    const rect = this.canvas.getBoundingClientRect();
    const sx = this.canvas.width / rect.width;
    const sy = this.canvas.height / rect.height;
    return { x: (e.clientX - rect.left) * sx, y: (e.clientY - rect.top) * sy };
  }

  private padFromMouse(e: MouseEvent): { x: number; y: number } {
    const screenPt = this.mouseToCanvas(e);
    const vp = this.viewport();
    const stagePt = screenToStage(screenPt, vp);
    const padX = Math.max(0, Math.min(1, stagePt.x / this.layout.width_m + 0.5));
    const padY = Math.max(0, Math.min(1, 0.5 - stagePt.y / this.layout.depth_m));
    return { x: padX, y: padY };
  }

  private emitHand(e: MouseEvent): void {
    const pad = this.padFromMouse(e);
    this.handPadPos = pad;
    this.cbs.onHandMove?.(pad.x, pad.y);
    this.scheduleDraw();
  }

  private onMouseDown = (e: MouseEvent): void => {
    if (this.handMode) {
      this.handDragging = true;
      this.emitHand(e);
      return;
    }
    const screenPt = this.mouseToCanvas(e);
    const vp = this.viewport();
    const stagePt = screenToStage(screenPt, vp);
    for (const bar of [...this.layout.bars].reverse()) {
      if (hitTestBar(bar, screenPt, vp, 16)) {
        this.selectBar(bar.id);
        this.drag = {
          kind: e.shiftKey ? "rotate" : "move",
          barId: bar.id,
          startStage: stagePt,
          startPose: { x: bar.pose.x_m, y: bar.pose.y_m, rot: bar.pose.rotation_rad },
        };
        return;
      }
    }
    this.selectBar(null);
  };

  private onMouseMove = (e: MouseEvent): void => {
    if (this.handMode) {
      if (this.handDragging) this.emitHand(e);
      return;
    }
    if (!this.drag) return;
    const screenPt = this.mouseToCanvas(e);
    const vp = this.viewport();
    const stagePt = screenToStage(screenPt, vp);
    const bar = this.layout.bars.find((b) => b.id === this.drag!.barId);
    if (!bar) return;
    if (this.drag.kind === "move") {
      const dx = stagePt.x - this.drag.startStage.x;
      const dy = stagePt.y - this.drag.startStage.y;
      this.layout = {
        ...this.layout,
        bars: this.layout.bars.map((b) =>
          b.id === bar.id
            ? {
                ...b,
                pose: {
                  ...b.pose,
                  x_m: this.drag!.startPose.x + dx,
                  y_m: this.drag!.startPose.y + dy,
                },
              }
            : b,
        ),
      };
    } else {
      const angle = Math.atan2(
        stagePt.y - this.drag.startPose.y,
        stagePt.x - this.drag.startPose.x,
      );
      this.layout = {
        ...this.layout,
        bars: this.layout.bars.map((b) =>
          b.id === bar.id ? { ...b, pose: { ...b.pose, rotation_rad: angle } } : b,
        ),
      };
    }
    this.cbs.onLayoutChange(this.layout);
    this.scheduleDraw();
  };

  private onMouseUp = (): void => {
    this.drag = null;
    this.handDragging = false;
  };
}
