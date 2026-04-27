import { BeatDetector } from "./inputs/audio.js";
import { startHandTracker, type HandTrackerHandle } from "./inputs/handTracker.js";
import { SpinWheel } from "./inputs/spinWheel.js";
import { TapTempo } from "./inputs/tapTempo.js";
import { PresetPanel } from "./presets/PresetPanel.js";
import { StageDesigner } from "./stage/StageDesigner.js";
import { StagePreview } from "./stage/StagePreview.js";
import { makeDefaultBar } from "./stage/geometry.js";
import { Store } from "./state/store.js";
import { getLayout, putLayout } from "./transport/api.js";
import { Bridge } from "./transport/bridge.js";
import type { LedFrame, StageLayout } from "./types.js";

const LAYOUT_NAME = "sample-5bar";

export async function bootstrap(root: HTMLElement): Promise<void> {
  const layoutStore = new Store<StageLayout>(await getLayout(LAYOUT_NAME));
  const frameStore = new Store<LedFrame | null>(null);

  root.innerHTML = `
    <div class="app">
      <section class="pane pane-stage">
        <h2>Stage Designer <span class="muted">(click bar to select; shift+drag to rotate)</span></h2>
        <canvas id="stage-canvas" width="1200" height="800"></canvas>
      </section>
      <section class="pane pane-preview">
        <h2>Live Preview</h2>
        <canvas id="preview-canvas" width="1200" height="220"></canvas>
      </section>
      <section class="pane pane-controls">
        <h2>Controls</h2>
        <div class="row">
          <button id="add-bar">+ Add bar</button>
          <button id="remove-bar">Remove selected</button>
          <button id="save-layout">Save layout</button>
        </div>
        <div id="bar-fields"></div>
        <hr style="border-color: var(--line); margin: 12px 0;" />
        <h2>Inputs <span class="muted">(in-app demo controls work without webcam/mic)</span></h2>
        <div class="row">
          <button id="manual-trigger">Trigger pulse</button>
          <button id="tap-tempo">Tap tempo</button>
          <button id="auto-tempo">Lock &amp; loop</button>
          <button id="reset-tempo">Reset</button>
          <span id="bpm" class="muted">bpm: --</span>
        </div>
        <div class="row">
          <button id="audio-toggle">Start mic / beat detect</button>
        </div>
        <div class="row">
          <button id="hand-mode">Hand mode (drag stage)</button>
        </div>
        <div class="row">
          <button id="hand-toggle">Start webcam / hand follow</button>
          <video id="selfie" class="selfie" muted playsinline></video>
        </div>
        <div class="row spinwheel">
          <canvas id="spin-canvas" width="180" height="180"></canvas>
          <span class="muted">Drag to spin -> spin events</span>
        </div>
        <hr style="border-color: var(--line); margin: 12px 0;" />
        <h2>Presets</h2>
        <div id="preset-panel"></div>
      </section>
    </div>
  `;

  const stageCanvas = root.querySelector<HTMLCanvasElement>("#stage-canvas")!;
  const previewCanvas = root.querySelector<HTMLCanvasElement>("#preview-canvas")!;
  const designer = new StageDesigner(stageCanvas, layoutStore.get(), {
    onLayoutChange: (l) => layoutStore.set(l),
    onSelect: (id) => renderBarFields(id),
    onHandMove: (x, y) => {
      bridge.send({
        kind: "hand_position",
        timestamp_ms: performance.now(),
        payload: { hand: "virtual", x, y },
      });
    },
  });
  const preview = new StagePreview(previewCanvas, layoutStore.get());

  const bridge = new Bridge(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/bridge`);
  bridge.onFrame((frame) => frameStore.set(frame));
  bridge.start();

  layoutStore.subscribe((l) => {
    designer.setLayout(l);
    preview.setLayout(l);
  });
  frameStore.subscribe((f) => {
    if (f) {
      designer.setFrame(f);
      preview.draw(f);
    }
  });

  // Toolbar wiring.
  root.querySelector<HTMLButtonElement>("#add-bar")!.addEventListener("click", () => {
    designer.addBar(makeDefaultBar(layoutStore.get().bars));
  });
  root.querySelector<HTMLButtonElement>("#remove-bar")!.addEventListener("click", () => {
    const sel = designer.selectedBar();
    if (sel) designer.removeBar(sel.id);
  });
  root.querySelector<HTMLButtonElement>("#save-layout")!.addEventListener("click", async () => {
    await putLayout(LAYOUT_NAME, layoutStore.get());
  });

  const fieldsHost = root.querySelector<HTMLDivElement>("#bar-fields")!;
  function renderBarFields(barId: string | null): void {
    fieldsHost.innerHTML = "";
    if (!barId) return;
    const bar = layoutStore.get().bars.find((b) => b.id === barId);
    if (!bar) return;
    const make = (label: string, value: number, onChange: (n: number) => void): HTMLLabelElement => {
      const wrap = document.createElement("label");
      wrap.className = "field";
      const span = document.createElement("span");
      span.textContent = label;
      const input = document.createElement("input");
      input.type = "number";
      input.step = "0.01";
      input.value = String(value);
      input.addEventListener("change", () => onChange(Number(input.value)));
      wrap.appendChild(span);
      wrap.appendChild(input);
      return wrap;
    };
    fieldsHost.appendChild(make("length (m)", bar.length_m, (v) => designer.updateSelectedBar({ length_m: v })));
    fieldsHost.appendChild(
      make("segments", bar.segments, (v) => designer.updateSelectedBar({ segments: Math.max(1, Math.round(v)) })),
    );
    fieldsHost.appendChild(make("x (m)", bar.pose.x_m, (v) => designer.updateSelectedBar({ pose: { x_m: v } })));
    fieldsHost.appendChild(make("y (m)", bar.pose.y_m, (v) => designer.updateSelectedBar({ pose: { y_m: v } })));
    fieldsHost.appendChild(
      make("rotation (rad)", bar.pose.rotation_rad, (v) => designer.updateSelectedBar({ pose: { rotation_rad: v } })),
    );
  }

  // Inputs.
  const bpmEl = root.querySelector<HTMLSpanElement>("#bpm")!;

  root.querySelector<HTMLButtonElement>("#manual-trigger")!.addEventListener("click", () => {
    bridge.send({
      kind: "manual",
      timestamp_ms: performance.now(),
      payload: { action: "trigger" },
    });
  });

  const autoBtn = root.querySelector<HTMLButtonElement>("#auto-tempo")!;
  const tap = new TapTempo(bridge, {
    onBpm: (bpm) => {
      bpmEl.textContent = `bpm: ${bpm || "--"}`;
    },
    onAutoChange: (running) => {
      autoBtn.classList.toggle("armed", running);
      autoBtn.textContent = running ? "Stop loop" : "Lock & loop";
    },
  });
  root.querySelector<HTMLButtonElement>("#tap-tempo")!.addEventListener("click", () => tap.tap());
  autoBtn.addEventListener("click", () => {
    if (tap.autoRunning) tap.stopAuto();
    else tap.startAuto();
  });
  root.querySelector<HTMLButtonElement>("#reset-tempo")!.addEventListener("click", () => tap.reset());

  const handModeBtn = root.querySelector<HTMLButtonElement>("#hand-mode")!;
  handModeBtn.addEventListener("click", () => {
    const next = !designer.isHandMode();
    designer.setHandMode(next);
    handModeBtn.classList.toggle("armed", next);
    handModeBtn.textContent = next ? "Hand mode: ON" : "Hand mode (drag stage)";
  });

  let beatDetector: BeatDetector | null = null;
  root.querySelector<HTMLButtonElement>("#audio-toggle")!.addEventListener("click", async (e) => {
    const btn = e.currentTarget as HTMLButtonElement;
    if (beatDetector) {
      beatDetector.stop();
      beatDetector = null;
      btn.textContent = "Start mic / beat detect";
      bpmEl.textContent = "bpm: --";
      return;
    }
    beatDetector = new BeatDetector(bridge, {
      threshold: 1.4,
      refractoryMs: 220,
      windowMs: 1500,
      lowPassHz: 200,
    }, (bpm) => {
      bpmEl.textContent = `bpm: ${bpm}`;
    });
    await beatDetector.start();
    btn.textContent = "Stop mic";
  });

  let handHandle: HandTrackerHandle | null = null;
  const selfie = root.querySelector<HTMLVideoElement>("#selfie")!;
  root.querySelector<HTMLButtonElement>("#hand-toggle")!.addEventListener("click", async (e) => {
    const btn = e.currentTarget as HTMLButtonElement;
    if (handHandle) {
      handHandle.stop();
      handHandle = null;
      btn.textContent = "Start webcam / hand follow";
      return;
    }
    handHandle = await startHandTracker(selfie, bridge);
    btn.textContent = "Stop webcam";
  });

  new SpinWheel(root.querySelector<HTMLCanvasElement>("#spin-canvas")!, bridge);

  const presetPanel = new PresetPanel(root.querySelector<HTMLDivElement>("#preset-panel")!);
  await presetPanel.refresh();
}
