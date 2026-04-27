import { describe, expect, it } from "vitest";

import {
  barEndpoints,
  cameraXToStageX,
  hitTestBar,
  makeDefaultBar,
  pixelFor,
  segmentCentre,
  stageToScreen,
  screenToStage,
} from "../src/stage/geometry.js";
import type { Bar, LedFrame } from "../src/types.js";

const horizontalBar: Bar = {
  id: "h",
  length_m: 2,
  segments: 5,
  pose: { x_m: 0, y_m: 0, rotation_rad: 0 },
};

describe("geometry", () => {
  it("stageToScreen <-> screenToStage round trip", () => {
    const vp = { width: 800, height: 600, pixelsPerMetre: 100 };
    const screen = stageToScreen({ x: 1, y: 0.5 }, vp);
    expect(screen).toEqual({ x: 500, y: 250 });
    expect(screenToStage(screen, vp)).toEqual({ x: 1, y: 0.5 });
  });

  it("barEndpoints place bar along local x axis", () => {
    const [a, b] = barEndpoints(horizontalBar);
    expect(a).toEqual({ x: -1, y: 0 });
    expect(b).toEqual({ x: 1, y: 0 });
  });

  it("hitTestBar matches a click on the line", () => {
    const vp = { width: 800, height: 600, pixelsPerMetre: 100 };
    const onBar = stageToScreen({ x: 0, y: 0 }, vp);
    expect(hitTestBar(horizontalBar, onBar, vp)).toBe(true);
    const farAway = stageToScreen({ x: 5, y: 5 }, vp);
    expect(hitTestBar(horizontalBar, farAway, vp)).toBe(false);
  });

  it("segmentCentre evenly spaces segments", () => {
    const ends = [segmentCentre(horizontalBar, 0), segmentCentre(horizontalBar, 4)];
    expect(ends[0]!.x).toBeCloseTo(-1);
    expect(ends[1]!.x).toBeCloseTo(1);
    expect(segmentCentre(horizontalBar, 2).x).toBeCloseTo(0);
  });

  it("cameraXToStageX mirrors and centres", () => {
    const layout = { name: "t", width_m: 4, depth_m: 2, bars: [] };
    expect(cameraXToStageX(layout, 0)).toBeCloseTo(2);   // camera-left -> stage-right after mirror
    expect(cameraXToStageX(layout, 1)).toBeCloseTo(-2);
    expect(cameraXToStageX(layout, 0.5)).toBeCloseTo(0);
  });

  it("pixelFor returns matching pixel or undefined", () => {
    const frame: LedFrame = {
      layoutVersion: 0,
      timestampMs: 0,
      bars: [{ barId: "h", pixels: [[10, 20, 30]] }],
    };
    expect(pixelFor(frame, "h", 0)).toEqual([10, 20, 30]);
    expect(pixelFor(frame, "missing", 0)).toBeUndefined();
  });

  it("makeDefaultBar avoids id collisions", () => {
    const bars: Bar[] = [
      { ...horizontalBar, id: "bar-1" },
      { ...horizontalBar, id: "bar-2" },
    ];
    const next = makeDefaultBar(bars);
    expect(next.id).toBe("bar-3");
  });

  it("stage coords map back to pad coords for hand mode", () => {
    // Pad-bottom-middle (x=0.5, y=1.0) corresponds to stage front-centre.
    const layout = { name: "t", width_m: 6, depth_m: 2.5, bars: [] };
    const padX = 0.5;
    const padY = 1.0;
    const stageX = (padX - 0.5) * layout.width_m;
    const stageY = (0.5 - padY) * layout.depth_m;
    expect(stageX).toBe(0);
    expect(stageY).toBe(-1.25);

    const back = {
      x: stageX / layout.width_m + 0.5,
      y: 0.5 - stageY / layout.depth_m,
    };
    expect(back.x).toBe(padX);
    expect(back.y).toBe(padY);
  });
});
