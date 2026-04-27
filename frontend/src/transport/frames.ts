import type { LedFrame, RGB } from "../types.js";

/**
 * Decode the binary `LedFrame` packet emitted by the backend simulator sink.
 *
 * Wire format mirrors `backend/dj_lights/outputs/simulator.py`:
 *   u16 layout_version, u16 bar_count, f64 timestamp_ms,
 *   then for each bar: u8 id_len, utf8 id, u16 pixel_count, RGB bytes.
 */
export function decodeFrame(buffer: ArrayBuffer): LedFrame {
  const view = new DataView(buffer);
  let cursor = 0;
  const layoutVersion = view.getUint16(cursor, false);
  cursor += 2;
  const barCount = view.getUint16(cursor, false);
  cursor += 2;
  const timestampMs = view.getFloat64(cursor, false);
  cursor += 8;
  const bars = [];
  const decoder = new TextDecoder("utf-8");
  for (let i = 0; i < barCount; i++) {
    const idLen = view.getUint8(cursor);
    cursor += 1;
    const idBytes = new Uint8Array(buffer, cursor, idLen);
    const barId = decoder.decode(idBytes);
    cursor += idLen;
    const pixelCount = view.getUint16(cursor, false);
    cursor += 2;
    const pixels: RGB[] = new Array(pixelCount);
    for (let p = 0; p < pixelCount; p++) {
      pixels[p] = [
        view.getUint8(cursor),
        view.getUint8(cursor + 1),
        view.getUint8(cursor + 2),
      ];
      cursor += 3;
    }
    bars.push({ barId, pixels });
  }
  return { layoutVersion, timestampMs, bars };
}
