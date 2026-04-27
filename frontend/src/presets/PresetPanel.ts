import {
  armPreset,
  disarmPreset,
  listPresets,
} from "../transport/api.js";
import type { PresetMeta } from "../types.js";

export class PresetPanel {
  private root: HTMLElement;
  private items = new Map<string, HTMLButtonElement>();

  constructor(parent: HTMLElement) {
    this.root = document.createElement("div");
    parent.appendChild(this.root);
  }

  async refresh(): Promise<void> {
    const presets = await listPresets();
    this.render(presets);
  }

  private render(presets: PresetMeta[]): void {
    this.root.innerHTML = "";
    for (const p of presets) {
      const card = document.createElement("div");
      card.className = "preset-card";
      const name = document.createElement("div");
      name.textContent = p.name;
      const triggers = document.createElement("div");
      triggers.className = "muted";
      triggers.textContent = `triggers: ${p.triggers.join(", ")}`;
      const btn = document.createElement("button");
      btn.textContent = p.armed ? "Disarm" : "Arm";
      if (p.armed) btn.classList.add("armed");
      btn.addEventListener("click", async () => {
        if (btn.classList.contains("armed")) {
          await disarmPreset(p.name);
          btn.classList.remove("armed");
          btn.textContent = "Arm";
        } else {
          await armPreset(p.name);
          btn.classList.add("armed");
          btn.textContent = "Disarm";
        }
      });
      card.appendChild(name);
      card.appendChild(triggers);
      card.appendChild(btn);
      this.root.appendChild(card);
      this.items.set(p.name, btn);
    }
  }
}
