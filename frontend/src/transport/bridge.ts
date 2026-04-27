import type { DjEvent, LedFrame } from "../types.js";
import { decodeFrame } from "./frames.js";

export type FrameListener = (frame: LedFrame) => void;

/**
 * Combined inbound-frames / outbound-events WebSocket. Auto-reconnects with
 * a simple linear backoff so a backend restart during dev doesn't require a
 * page refresh.
 */
export class Bridge {
  private ws: WebSocket | null = null;
  private listeners: FrameListener[] = [];
  private queued: DjEvent[] = [];
  private retryMs = 500;
  private closed = false;

  constructor(private readonly url: string) {}

  start(): void {
    this.connect();
  }

  stop(): void {
    this.closed = true;
    this.ws?.close();
  }

  onFrame(fn: FrameListener): () => void {
    this.listeners.push(fn);
    return () => {
      this.listeners = this.listeners.filter((l) => l !== fn);
    };
  }

  send(event: DjEvent): void {
    const ts = event.timestamp_ms ?? performance.now();
    const message = JSON.stringify({ ...event, timestamp_ms: ts });
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(message);
    } else {
      this.queued.push({ ...event, timestamp_ms: ts });
    }
  }

  private connect(): void {
    if (this.closed) return;
    const ws = new WebSocket(this.url);
    ws.binaryType = "arraybuffer";
    this.ws = ws;
    ws.onopen = () => {
      this.retryMs = 500;
      while (this.queued.length > 0) {
        const ev = this.queued.shift();
        if (ev) ws.send(JSON.stringify(ev));
      }
    };
    ws.onmessage = (msg: MessageEvent) => {
      if (typeof msg.data === "string") {
        // Server-side error or status; ignore for the POC, log for dev.
        // eslint-disable-next-line no-console
        console.warn("bridge text:", msg.data);
        return;
      }
      const buffer = msg.data as ArrayBuffer;
      const frame = decodeFrame(buffer);
      for (const fn of this.listeners) fn(frame);
    };
    ws.onclose = () => {
      if (this.closed) return;
      const delay = this.retryMs;
      this.retryMs = Math.min(this.retryMs * 2, 5000);
      setTimeout(() => this.connect(), delay);
    };
    ws.onerror = () => {
      // onclose will follow.
    };
  }
}
