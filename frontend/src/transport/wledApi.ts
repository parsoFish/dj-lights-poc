export interface WledDevice {
  id: string;
  name: string;
  host: string;
  port: number;
  source: "mdns" | "manual";
}

export interface WledInfo {
  name: string;
  version: string;
  mac: string;
  led_count: number;
  fps: number;
}

export interface WledBinding {
  device_id: string;
  pixel_start: number;
  pixel_end: number;
  bar_id: string;
  reverse?: boolean;
}

export interface WledCalibration {
  layout_name: string;
  bindings: WledBinding[];
}

const base = "/api";

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}: ${await res.text()}`);
  }
  return (await res.json()) as T;
}

export async function listWledDevices(): Promise<WledDevice[]> {
  const res = await fetch(`${base}/wled/devices`);
  const body = await jsonOrThrow<{ devices: WledDevice[] }>(res);
  return body.devices;
}

export async function addWledDevice(host: string, name?: string, port = 80): Promise<WledDevice> {
  const res = await fetch(`${base}/wled/devices`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ host, name, port }),
  });
  return jsonOrThrow<WledDevice>(res);
}

export async function getWledInfo(deviceId: string): Promise<WledDevice & { info: WledInfo }> {
  const res = await fetch(`${base}/wled/devices/${encodeURIComponent(deviceId)}`);
  return jsonOrThrow<WledDevice & { info: WledInfo }>(res);
}

export async function getCalibration(layout: string): Promise<WledCalibration> {
  const res = await fetch(`${base}/wled/calibration/${encodeURIComponent(layout)}`);
  return jsonOrThrow<WledCalibration>(res);
}

export async function putCalibration(layout: string, calibration: WledCalibration): Promise<WledCalibration> {
  const res = await fetch(`${base}/wled/calibration/${encodeURIComponent(layout)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(calibration),
  });
  return jsonOrThrow<WledCalibration>(res);
}

export async function startMirror(deviceId: string): Promise<{ mirroring: boolean; led_count: number }> {
  const res = await fetch(`${base}/wled/mirror/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ device_id: deviceId }),
  });
  return jsonOrThrow<{ mirroring: boolean; led_count: number }>(res);
}

export async function stopMirror(): Promise<{ mirroring: boolean }> {
  const res = await fetch(`${base}/wled/mirror/stop`, { method: "POST" });
  return jsonOrThrow<{ mirroring: boolean }>(res);
}
