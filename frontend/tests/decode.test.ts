import { describe, expect, it } from "vitest";

import { decodeFrame } from "../src/transport/frames.js";

function buildFrame(): ArrayBuffer {
  const buf = new ArrayBuffer(12 + (1 + 1 + 2 + 6) + (1 + 1 + 2 + 3));
  const view = new DataView(buf);
  let cursor = 0;
  view.setUint16(cursor, 7, false); cursor += 2;
  view.setUint16(cursor, 2, false); cursor += 2;
  view.setFloat64(cursor, 33.5, false); cursor += 8;
  // bar "a"
  view.setUint8(cursor, 1); cursor += 1;
  view.setUint8(cursor, "a".charCodeAt(0)); cursor += 1;
  view.setUint16(cursor, 2, false); cursor += 2;
  view.setUint8(cursor, 10); cursor += 1;
  view.setUint8(cursor, 20); cursor += 1;
  view.setUint8(cursor, 30); cursor += 1;
  view.setUint8(cursor, 40); cursor += 1;
  view.setUint8(cursor, 50); cursor += 1;
  view.setUint8(cursor, 60); cursor += 1;
  // bar "b"
  view.setUint8(cursor, 1); cursor += 1;
  view.setUint8(cursor, "b".charCodeAt(0)); cursor += 1;
  view.setUint16(cursor, 1, false); cursor += 2;
  view.setUint8(cursor, 1); cursor += 1;
  view.setUint8(cursor, 2); cursor += 1;
  view.setUint8(cursor, 3); cursor += 1;
  return buf;
}

describe("decodeFrame", () => {
  it("decodes header and pixels", () => {
    const frame = decodeFrame(buildFrame());
    expect(frame.layoutVersion).toBe(7);
    expect(frame.timestampMs).toBe(33.5);
    expect(frame.bars).toHaveLength(2);
    expect(frame.bars[0]!.barId).toBe("a");
    expect(frame.bars[0]!.pixels).toEqual([
      [10, 20, 30],
      [40, 50, 60],
    ]);
    expect(frame.bars[1]!.pixels).toEqual([[1, 2, 3]]);
  });
});
