# Architectural Decisions

Lightweight ADR log. Each entry: context, decision, consequences. Most recent
last.

## ADR-001 — Python backend + vanilla TypeScript frontend

**Context.** Other projects in the user's portfolio mostly split on Python
(CLI / agent work) and vanilla TypeScript + Canvas (visual / interactive
work). The POC has both shapes: a backend lighting engine (great fit for
Python + asyncio + future PyTorch on the Orin Nano) and a visual editor
(great fit for Vite + Canvas).

**Decision.** Python 3.12 + Click + FastAPI on the backend. Vanilla TS + Vite
+ HTML5 Canvas on the frontend. No React, no Three.js for the POC.

**Consequences.** Familiar shape for the user; reuses test/lint conventions
from existing projects (pytest/ruff/mypy + Vitest/Playwright). The 2D
top-down designer matches the user's hand-drawn layout. A future 3D upgrade
can swap Canvas for Three.js without changing the backend or transport.

## ADR-002 — Output is abstracted behind `OutputSink`

**Context.** Originally the friend's bars were hand-built and the wire
protocol unknown; we shipped an `ArtNetSink` stub against the abstract
`OutputSink` interface so the POC could land before the protocol was
confirmed.

**Update (Phase 6).** The friend's hardware turned out to be WLED firmware
on a QuinLED ESP-32, not raw Art-Net. The Art-Net stub was retired in
favour of a WLED-native client (`wled/client.py`, `wled/live_ws.py`). The
`OutputSink` protocol stays — Phase 7's WLED-realtime override path
implements it for write-side compositing.

## ADR-003 — Browser MediaPipe Hands now, Orin Nano later

**Context.** The user owns an NVIDIA Orin Nano and wants the POC to "show off
some of the specific use cases" including gesture / hand-following. Wiring
TensorRT inference takes time and a webcam pipeline that may not exist on
the dev machine.

**Decision.** Run MediaPipe Hands (WASM/JS) in the browser for the POC. The
event payload (`{hand, x, y}`) is the same one the Orin worker will produce.
Scaffold `inputs/cv_orin_stub.py` with the same shape so future agents only
need to fill the inference body.

**Consequences.** Demoable today on any laptop with a webcam. The contract
that survives the upgrade is `Event(kind="hand_position", payload={...})` —
nothing else has to change.

## ADR-004 — Presets as Python classes (no DSL yet)

**Context.** The user mentioned a "modular preset" idea where actions trigger
specific patterns. The full vision is an in-app preset authoring tool.

**Decision.** For the POC, presets are hand-written `dataclass` classes that
implement `Preset.on_event` + `Preset.render`. Each one is a thin glue
between an event kind and an `Effect` (which holds the rendering math).

**Consequences.** Adding a preset is "subclass + register" — five-minute job.
The structure is already shaped like the eventual DSL (trigger kind +
effect + target group + params), so swapping in a JSON/YAML loader later
won't require redesign.

## ADR-006 — Sidecar to LedFx + WLED, never in the middle

**Context.** The friend's existing rig is LedFx → Art-Net → WLED → LEDs.
Phase 6 adds our app to give him a stage preview; later phases add control
plane and custom presets. Two architectures fit: literally proxy the
Art-Net stream (sit between LedFx and WLED) or run as a sibling that reads
WLED's state via its own WebSocket.

**Decision.** Sidecar. We subscribe to WLED's `/ws` `lv:true` stream as a
read-only consumer; we never intercept Art-Net. Phase 7 will write to WLED
directly via its realtime WS protocol *only* when our custom presets take
over (not as a continuous proxy).

**Consequences.** Reliability win — if our app crashes, his show keeps
running because the LedFx → WLED data path is untouched. No latency added
to LedFx's audio reactivity. Constraint accepted: WLED only allows one
live subscriber at a time, so coordinating with LedFx's frontend is
necessary if a user has both open. The frontend rarely subscribes; the
collision is theoretical for the friend's setup.

## ADR-005 — Channel-max compositing for layered presets

**Context.** Multiple armed presets may target overlapping bars (e.g. a
background pulse + a foreground spotlight). They must coexist without one
zeroing the other.

**Decision.** Composite layered preset frames via per-channel `max` blend.
Simple, idempotent, and keeps the brightest source visible without
saturating to white the way additive blend would.

**Consequences.** Good enough for the POC's scenarios. If we need additive
or alpha-aware blending later we can introduce a per-effect blend mode
without changing the engine.
