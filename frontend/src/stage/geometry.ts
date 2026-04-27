import type { Bar, LedFrame, RGB, StageLayout } from "../types.js";

/**
 * Stage-coordinate <-> screen-coordinate helpers for the top-down designer.
 * Stage origin (0,0) is the centre; positive x is right, positive y is "back"
 * away from the audience, matching the top-down sketch.
 */
export interface Viewport {
  width: number;
  height: number;
  pixelsPerMetre: number;
}

export function stageToScreen(point: { x: number; y: number }, vp: Viewport): { x: number; y: number } {
  return {
    x: vp.width / 2 + point.x * vp.pixelsPerMetre,
    y: vp.height / 2 - point.y * vp.pixelsPerMetre,
  };
}

export function screenToStage(point: { x: number; y: number }, vp: Viewport): { x: number; y: number } {
  return {
    x: (point.x - vp.width / 2) / vp.pixelsPerMetre,
    y: (vp.height / 2 - point.y) / vp.pixelsPerMetre,
  };
}

/** Endpoints of a bar in stage coordinates (length is along its local x-axis). */
export function barEndpoints(bar: Bar): [{ x: number; y: number }, { x: number; y: number }] {
  const half = bar.length_m / 2;
  const cos = Math.cos(bar.pose.rotation_rad);
  const sin = Math.sin(bar.pose.rotation_rad);
  return [
    { x: bar.pose.x_m - half * cos, y: bar.pose.y_m - half * sin },
    { x: bar.pose.x_m + half * cos, y: bar.pose.y_m + half * sin },
  ];
}

/** True iff the screen point lies within `tolerancePx` of the bar's line. */
export function hitTestBar(bar: Bar, screenPt: { x: number; y: number }, vp: Viewport, tolerancePx = 12): boolean {
  const [a, b] = barEndpoints(bar);
  const sa = stageToScreen(a, vp);
  const sb = stageToScreen(b, vp);
  const dx = sb.x - sa.x;
  const dy = sb.y - sa.y;
  const len2 = dx * dx + dy * dy;
  if (len2 === 0) return false;
  let t = ((screenPt.x - sa.x) * dx + (screenPt.y - sa.y) * dy) / len2;
  t = Math.max(0, Math.min(1, t));
  const projX = sa.x + t * dx;
  const projY = sa.y + t * dy;
  const distSq = (screenPt.x - projX) ** 2 + (screenPt.y - projY) ** 2;
  return distSq <= tolerancePx * tolerancePx;
}

/** Centre position of a single segment along a bar in stage coordinates. */
export function segmentCentre(bar: Bar, segmentIndex: number): { x: number; y: number } {
  if (bar.segments < 1) {
    throw new Error(`bar ${bar.id} has no segments`);
  }
  const local =
    bar.segments === 1 ? 0 : -bar.length_m / 2 + (segmentIndex / (bar.segments - 1)) * bar.length_m;
  const cos = Math.cos(bar.pose.rotation_rad);
  const sin = Math.sin(bar.pose.rotation_rad);
  return { x: bar.pose.x_m + local * cos, y: bar.pose.y_m + local * sin };
}

/** Map a normalised x in [0,1] across the camera frame to a stage x in metres. */
export function cameraXToStageX(layout: StageLayout, x01: number): number {
  const clamped = Math.max(0, Math.min(1, x01));
  // Mirror so the DJ's right-hand on-screen lines up with the audience-right bar.
  return -(clamped - 0.5) * layout.width_m;
}

/** Look up an RGB pixel for a given segment in the most recent frame. */
export function pixelFor(frame: LedFrame, barId: string, segmentIndex: number): RGB | undefined {
  const barFrame = frame.bars.find((b) => b.barId === barId);
  if (!barFrame) return undefined;
  return barFrame.pixels[segmentIndex];
}

/** Generate a default bar inserted into the stage at a sensible position. */
export function makeDefaultBar(existing: Bar[]): Bar {
  let n = existing.length + 1;
  let id = `bar-${n}`;
  while (existing.some((b) => b.id === id)) {
    n += 1;
    id = `bar-${n}`;
  }
  return {
    id,
    length_m: 1.5,
    segments: 20,
    pose: { x_m: 0, y_m: 0, rotation_rad: 0 },
  };
}
