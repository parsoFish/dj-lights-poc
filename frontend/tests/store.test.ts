import { describe, expect, it, vi } from "vitest";

import { Store } from "../src/state/store.js";

describe("Store", () => {
  it("notifies subscribers on change", () => {
    const s = new Store(0);
    const fn = vi.fn();
    s.subscribe(fn);
    s.set(1);
    expect(fn).toHaveBeenCalledWith(1);
  });

  it("does not notify when value is identical", () => {
    const s = new Store("a");
    const fn = vi.fn();
    s.subscribe(fn);
    s.set("a");
    expect(fn).not.toHaveBeenCalled();
  });

  it("update applies a function", () => {
    const s = new Store({ n: 1 });
    s.update((v) => ({ n: v.n + 1 }));
    expect(s.get().n).toBe(2);
  });

  it("unsubscribe stops notifications", () => {
    const s = new Store(0);
    const fn = vi.fn();
    const off = s.subscribe(fn);
    off();
    s.set(1);
    expect(fn).not.toHaveBeenCalled();
  });
});
