import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  addWledDevice,
  getCalibration,
  listWledDevices,
  putCalibration,
  startMirror,
  stopMirror,
} from "../src/transport/wledApi.js";

const fakeFetch = vi.fn();

function jsonResponse(body: unknown, ok = true): Response {
  return {
    ok,
    status: ok ? 200 : 500,
    statusText: ok ? "OK" : "ERR",
    text: async () => JSON.stringify(body),
    json: async () => body,
  } as unknown as Response;
}

describe("wledApi", () => {
  beforeEach(() => {
    fakeFetch.mockReset();
    vi.stubGlobal("fetch", fakeFetch);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("listWledDevices unwraps the {devices} envelope", async () => {
    fakeFetch.mockResolvedValueOnce(jsonResponse({ devices: [{ id: "x", name: "x", host: "h", port: 80, source: "mdns" }] }));
    const devices = await listWledDevices();
    expect(devices).toHaveLength(1);
    expect(devices[0]!.id).toBe("x");
  });

  it("addWledDevice POSTs host/name/port", async () => {
    fakeFetch.mockResolvedValueOnce(jsonResponse({ id: "manual:1.2.3.4:80", name: "n", host: "1.2.3.4", port: 80, source: "manual" }));
    await addWledDevice("1.2.3.4", "n");
    const call = fakeFetch.mock.calls[0]!;
    expect(call[0]).toBe("/api/wled/devices");
    expect(call[1].method).toBe("POST");
    const body = JSON.parse(call[1].body as string);
    expect(body).toEqual({ host: "1.2.3.4", name: "n", port: 80 });
  });

  it("calibration round trip uses the layout name", async () => {
    fakeFetch.mockResolvedValueOnce(jsonResponse({ layout_name: "L", bindings: [] }));
    const cal = await getCalibration("L");
    expect(cal.layout_name).toBe("L");

    fakeFetch.mockResolvedValueOnce(jsonResponse({ layout_name: "L", bindings: [{ device_id: "d", pixel_start: 0, pixel_end: 4, bar_id: "a" }] }));
    const saved = await putCalibration("L", { layout_name: "L", bindings: [{ device_id: "d", pixel_start: 0, pixel_end: 4, bar_id: "a" }] });
    expect(saved.bindings).toHaveLength(1);
  });

  it("startMirror posts the device id; stopMirror takes no body", async () => {
    fakeFetch.mockResolvedValueOnce(jsonResponse({ mirroring: true, led_count: 100 }));
    await startMirror("dev-1");
    expect(JSON.parse(fakeFetch.mock.calls[0]![1].body as string)).toEqual({ device_id: "dev-1" });

    fakeFetch.mockResolvedValueOnce(jsonResponse({ mirroring: false }));
    await stopMirror();
    expect(fakeFetch.mock.calls[1]![1].body).toBeUndefined();
  });

  it("throws on non-2xx", async () => {
    fakeFetch.mockResolvedValueOnce(jsonResponse({ error: "no" }, false));
    await expect(listWledDevices()).rejects.toThrow();
  });
});
