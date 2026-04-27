export interface Pose2D {
  x_m: number;
  y_m: number;
  rotation_rad: number;
}

export interface Bar {
  id: string;
  length_m: number;
  segments: number;
  pose: Pose2D;
}

export interface StageLayout {
  name: string;
  width_m: number;
  depth_m: number;
  bars: Bar[];
}

export type RGB = [number, number, number];

export interface BarFrame {
  barId: string;
  pixels: RGB[];
}

export interface LedFrame {
  layoutVersion: number;
  timestampMs: number;
  bars: BarFrame[];
}

export type EventKind = "beat" | "hand_position" | "spin" | "manual" | "heartbeat";

export interface DjEvent {
  kind: EventKind;
  timestamp_ms?: number;
  payload: Record<string, unknown>;
}

export interface PresetMeta {
  name: string;
  triggers: EventKind[];
  armed: boolean;
}
