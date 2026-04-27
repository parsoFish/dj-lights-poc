import type { PresetMeta, StageLayout } from "../types.js";

const base = "/api";

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return (await res.json()) as T;
}

export async function listLayouts(): Promise<string[]> {
  const res = await fetch(`${base}/layouts`);
  const body = await jsonOrThrow<{ layouts: string[] }>(res);
  return body.layouts;
}

export async function getLayout(name: string): Promise<StageLayout> {
  const res = await fetch(`${base}/layouts/${encodeURIComponent(name)}`);
  return jsonOrThrow<StageLayout>(res);
}

export async function putLayout(name: string, layout: StageLayout): Promise<StageLayout> {
  const res = await fetch(`${base}/layouts/${encodeURIComponent(name)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(layout),
  });
  return jsonOrThrow<StageLayout>(res);
}

export async function listPresets(): Promise<PresetMeta[]> {
  const res = await fetch(`${base}/presets`);
  const body = await jsonOrThrow<{ presets: PresetMeta[] }>(res);
  return body.presets;
}

export async function armPreset(name: string): Promise<void> {
  const res = await fetch(`${base}/presets/${encodeURIComponent(name)}/arm`, {
    method: "POST",
  });
  await jsonOrThrow(res);
}

export async function disarmPreset(name: string): Promise<void> {
  const res = await fetch(`${base}/presets/${encodeURIComponent(name)}/disarm`, {
    method: "POST",
  });
  await jsonOrThrow(res);
}
