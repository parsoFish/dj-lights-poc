/**
 * Tiny pub/sub store. No framework — just a typed listener list.
 * Future agents needing more (selectors, derived state) can swap in a
 * framework without touching consumers thanks to the narrow API.
 */
export class Store<T> {
  private listeners = new Set<(value: T) => void>();
  constructor(private value: T) {}

  get(): T {
    return this.value;
  }

  set(next: T): void {
    if (Object.is(next, this.value)) return;
    this.value = next;
    for (const l of this.listeners) l(this.value);
  }

  update(updater: (current: T) => T): void {
    this.set(updater(this.value));
  }

  subscribe(listener: (value: T) => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }
}
