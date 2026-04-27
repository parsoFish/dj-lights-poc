import type { Bridge } from "../transport/bridge.js";

/**
 * Hand tracking via @mediapipe/tasks-vision Hand Landmarker.
 *
 * Coordinates: MediaPipe returns landmarks in normalised [0,1] image space.
 * We mirror x so the DJ's right hand reads as audience-right. Only landmark
 * 9 (middle finger MCP) is sent for the POC -- a stable single point per
 * hand keeps the demo predictable; future agents can broaden to full skeleton.
 *
 * The Orin Nano replacement publishes the same `hand_position` payload, so
 * the engine and presets are unaffected when this is swapped out.
 */
export interface HandTrackerHandle {
  stop: () => void;
}

interface MediaPipeHandLandmarker {
  detectForVideo: (
    video: HTMLVideoElement,
    timestamp: number,
  ) => {
    landmarks: { x: number; y: number; z: number }[][];
    handedness: { categoryName: string }[][];
  };
  close: () => void;
}

export async function startHandTracker(
  video: HTMLVideoElement,
  bridge: Bridge,
): Promise<HandTrackerHandle> {
  const { FilesetResolver, HandLandmarker } = await import("@mediapipe/tasks-vision");
  const fileset = await FilesetResolver.forVisionTasks(
    "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision/wasm",
  );
  const landmarker = (await HandLandmarker.createFromOptions(fileset, {
    baseOptions: {
      modelAssetPath:
        "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
      delegate: "GPU",
    },
    runningMode: "VIDEO",
    numHands: 2,
  })) as unknown as MediaPipeHandLandmarker;

  const stream = await navigator.mediaDevices.getUserMedia({
    video: { facingMode: "user" },
  });
  video.srcObject = stream;
  await video.play();

  let cancelled = false;
  let lastTs = -1;

  const tick = (): void => {
    if (cancelled) return;
    if (video.readyState >= 2) {
      const ts = performance.now();
      if (ts !== lastTs) {
        lastTs = ts;
        const result = landmarker.detectForVideo(video, ts);
        for (let i = 0; i < result.landmarks.length; i++) {
          const lm = result.landmarks[i]?.[9];
          const handedness = result.handedness[i]?.[0]?.categoryName ?? "unknown";
          if (!lm) continue;
          bridge.send({
            kind: "hand_position",
            timestamp_ms: ts,
            payload: {
              hand: handedness.toLowerCase(),
              x: 1 - lm.x, // mirror
              y: lm.y,
            },
          });
        }
      }
    }
    requestAnimationFrame(tick);
  };
  tick();

  return {
    stop: () => {
      cancelled = true;
      stream.getTracks().forEach((t) => t.stop());
      landmarker.close();
    },
  };
}
