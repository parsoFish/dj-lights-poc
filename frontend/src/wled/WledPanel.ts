import {
  type WledBinding,
  type WledCalibration,
  type WledDevice,
  addWledDevice,
  getCalibration,
  getWledInfo,
  listWledDevices,
  putCalibration,
  startMirror,
  stopMirror,
} from "../transport/wledApi.js";
import type { StageLayout } from "../types.js";

export interface WledPanelCallbacks {
  layoutName: string;
  layout(): StageLayout;
  onMirrorChange?: (running: boolean) => void;
}

/**
 * Sidebar panel listing discovered WLED nodes, letting the user pick one to
 * inspect (LED count + a tiny calibration table mapping pixel ranges onto
 * bars), and toggling the live mirror on or off.
 *
 * The calibration UI is intentionally a small table editor rather than a
 * canvas-drawn range picker: it's fast to build, easy to test, and the user's
 * sample-5bar layout has 5 bars total — visually drawing 5 ranges adds
 * complexity without much win for Phase 6.
 */
export class WledPanel {
  private root: HTMLElement;
  private mirrorRunning = false;
  private mirrorDeviceId: string | null = null;
  private currentInfoLedCount: number | null = null;
  private currentDeviceId: string | null = null;
  private bindings: WledBinding[] = [];

  constructor(parent: HTMLElement, private readonly cbs: WledPanelCallbacks) {
    this.root = document.createElement("div");
    this.root.className = "wled-panel";
    parent.appendChild(this.root);
    this.render();
    this.refreshDevices().catch(console.warn);
    this.refreshCalibration().catch(console.warn);
    setInterval(() => {
      this.refreshDevices().catch(() => {});
    }, 5000);
  }

  private async refreshDevices(): Promise<void> {
    const devices = await listWledDevices();
    this.renderDeviceList(devices);
  }

  private async refreshCalibration(): Promise<void> {
    const cal = await getCalibration(this.cbs.layoutName);
    this.bindings = [...cal.bindings];
    this.renderBindings();
  }

  private async loadInfo(deviceId: string): Promise<void> {
    try {
      const detail = await getWledInfo(deviceId);
      this.currentDeviceId = deviceId;
      this.currentInfoLedCount = detail.info.led_count;
      this.renderInfo(detail);
    } catch (err) {
      this.currentDeviceId = deviceId;
      this.currentInfoLedCount = null;
      const target = this.root.querySelector<HTMLDivElement>(".wled-info");
      if (target) target.innerHTML = `<span class="muted">Could not reach ${deviceId}: ${String(err)}</span>`;
    }
  }

  private async toggleMirror(deviceId: string): Promise<void> {
    if (this.mirrorRunning) {
      await stopMirror();
      this.mirrorRunning = false;
      this.mirrorDeviceId = null;
    } else {
      await startMirror(deviceId);
      this.mirrorRunning = true;
      this.mirrorDeviceId = deviceId;
    }
    this.cbs.onMirrorChange?.(this.mirrorRunning);
    this.renderDeviceList(undefined);  // refresh button states
  }

  private async addManual(host: string, name: string): Promise<void> {
    await addWledDevice(host, name || undefined);
    await this.refreshDevices();
  }

  private async addBinding(): Promise<void> {
    if (!this.currentDeviceId) return;
    const layout = this.cbs.layout();
    const bar = layout.bars[0];
    if (!bar) return;
    this.bindings = [
      ...this.bindings,
      { device_id: this.currentDeviceId, pixel_start: 0, pixel_end: bar.segments, bar_id: bar.id, reverse: false },
    ];
    this.renderBindings();
  }

  private async saveBindings(): Promise<void> {
    const cal: WledCalibration = { layout_name: this.cbs.layoutName, bindings: this.bindings };
    await putCalibration(this.cbs.layoutName, cal);
  }

  private deleteBinding(index: number): void {
    this.bindings = this.bindings.filter((_, i) => i !== index);
    this.renderBindings();
  }

  private updateBinding(index: number, patch: Partial<WledBinding>): void {
    this.bindings = this.bindings.map((b, i) => (i === index ? { ...b, ...patch } : b));
  }

  // --- DOM ----------------------------------------------------------------

  private render(): void {
    this.root.innerHTML = `
      <div class="row">
        <strong>Discovered devices</strong>
      </div>
      <div class="wled-devices"></div>
      <div class="row">
        <input class="wled-host" placeholder="manual host / IP" />
        <input class="wled-name" placeholder="name (optional)" />
        <button class="wled-add">Add</button>
      </div>
      <div class="wled-info muted">Select a device to fetch its LED count.</div>
      <div class="row">
        <strong>Calibration</strong>
        <span class="muted">layout: ${this.cbs.layoutName}</span>
      </div>
      <div class="wled-bindings"></div>
      <div class="row">
        <button class="wled-add-binding">+ Binding</button>
        <button class="wled-save">Save calibration</button>
      </div>
    `;
    this.root
      .querySelector<HTMLButtonElement>(".wled-add")!
      .addEventListener("click", async () => {
        const host = this.root.querySelector<HTMLInputElement>(".wled-host")!;
        const name = this.root.querySelector<HTMLInputElement>(".wled-name")!;
        if (host.value.trim()) {
          await this.addManual(host.value.trim(), name.value.trim());
          host.value = "";
          name.value = "";
        }
      });
    this.root
      .querySelector<HTMLButtonElement>(".wled-add-binding")!
      .addEventListener("click", () => this.addBinding());
    this.root
      .querySelector<HTMLButtonElement>(".wled-save")!
      .addEventListener("click", () => this.saveBindings().catch(console.warn));
  }

  private renderDeviceList(devices: WledDevice[] | undefined): void {
    const host = this.root.querySelector<HTMLDivElement>(".wled-devices");
    if (!host) return;
    if (devices !== undefined) {
      host.dataset.devices = JSON.stringify(devices);
    }
    const list: WledDevice[] = JSON.parse(host.dataset.devices ?? "[]");
    host.innerHTML = "";
    if (list.length === 0) {
      host.innerHTML = '<span class="muted">No WLED nodes found yet (mDNS scanning…)</span>';
      return;
    }
    for (const d of list) {
      const row = document.createElement("div");
      row.className = "row";
      row.innerHTML = `
        <span style="flex:1">${d.name} <span class="muted">(${d.host}, ${d.source})</span></span>
        <button class="info" data-id="${d.id}">Info</button>
        <button class="mirror ${this.mirrorRunning && this.mirrorDeviceId === d.id ? "armed" : ""}" data-id="${d.id}">
          ${this.mirrorRunning && this.mirrorDeviceId === d.id ? "Stop mirror" : "Mirror"}
        </button>
      `;
      row
        .querySelector<HTMLButtonElement>(".info")!
        .addEventListener("click", () => this.loadInfo(d.id).catch(console.warn));
      row
        .querySelector<HTMLButtonElement>(".mirror")!
        .addEventListener("click", () => this.toggleMirror(d.id).catch(console.warn));
      host.appendChild(row);
    }
  }

  private renderInfo(detail: WledDevice & { info: { led_count: number; version: string; fps: number } }): void {
    const target = this.root.querySelector<HTMLDivElement>(".wled-info");
    if (!target) return;
    target.innerHTML = `
      <span class="muted">${detail.name} v${detail.info.version} · ${detail.info.led_count} LEDs · ${detail.info.fps} fps</span>
    `;
  }

  private renderBindings(): void {
    const host = this.root.querySelector<HTMLDivElement>(".wled-bindings");
    if (!host) return;
    host.innerHTML = "";
    const layout = this.cbs.layout();
    const ledCount = this.currentInfoLedCount ?? 0;
    this.bindings.forEach((b, i) => {
      const row = document.createElement("div");
      row.className = "row binding";
      row.innerHTML = `
        <input class="b-start" type="number" min="0" max="${ledCount || 9999}" value="${b.pixel_start}" style="width: 60px;" />
        <span class="muted">→</span>
        <input class="b-end" type="number" min="0" max="${ledCount || 9999}" value="${b.pixel_end}" style="width: 60px;" />
        <select class="b-bar">
          ${layout.bars.map((bar) => `<option value="${bar.id}" ${bar.id === b.bar_id ? "selected" : ""}>${bar.id}</option>`).join("")}
        </select>
        <label class="muted"><input class="b-rev" type="checkbox" ${b.reverse ? "checked" : ""}/> reverse</label>
        <button class="b-del">×</button>
      `;
      const start = row.querySelector<HTMLInputElement>(".b-start")!;
      const end = row.querySelector<HTMLInputElement>(".b-end")!;
      const barSel = row.querySelector<HTMLSelectElement>(".b-bar")!;
      const rev = row.querySelector<HTMLInputElement>(".b-rev")!;
      start.addEventListener("change", () => this.updateBinding(i, { pixel_start: Number(start.value) }));
      end.addEventListener("change", () => this.updateBinding(i, { pixel_end: Number(end.value) }));
      barSel.addEventListener("change", () => this.updateBinding(i, { bar_id: barSel.value }));
      rev.addEventListener("change", () => this.updateBinding(i, { reverse: rev.checked }));
      row.querySelector<HTMLButtonElement>(".b-del")!.addEventListener("click", () => this.deleteBinding(i));
      host.appendChild(row);
    });
  }
}
