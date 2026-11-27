# Architecture

## High-level dataflow

The app runs in two complementary modes:

```
  Standalone mode (no real hardware):

    [Audio] [MediaPipe] [Manual] [Spin]            [(future) Orin CV]
       \      |          |        /
        v     v          v       v
    +---------------------------------+
    |          Event Bus              |
    +---------------------------------+
                  |
                  v
    +---------------------------------+
    |  Engine (presets + compositing) |
    |  60 fps -> LedFrame             |
    +---------------------------------+
                  |
                  v
    [Simulator WS  ->  every browser]


  Mirror mode (Phase 6, sidecar to LedFx + WLED):

    [LedFx] -- Art-Net --> [WLED] -- pixels --> [LEDs]
                              ^
                              |  /ws lv:true (live frame stream)
                              v
                          [Our app]
                              |
                              v
    [Engine.mirror_mode = True; preset compositing suppressed]
                              |
                              v
    [Simulator WS  ->  every browser]
```

In mirror mode the engine still drains its event bus (so preset clocks stay
fresh) but does not produce frames; what every browser sees is whatever
WLED is rendering, decoded from its WebSocket. Phase 7 will add a write-side
override path so custom presets can take over WLED's output briefly.

## Module map

### Backend (`backend/dj_lights/`)

| Module | Responsibility |
|---|---|
| `engine/frame.py` | Immutable scene types: `Pose2D`, `Bar`, `StageLayout`, `BarFrame`, `LedFrame`. Source of truth for all wire payloads. |
| `engine/events.py` | `Event` dataclass + typed `EventKind`s + `EventBus` with overflow-drops-oldest semantics. |
| `engine/effects.py` | Composable `Effect`s (`Pulse`, `Spotlight`, `Chase`). Pure functions of `(layout, t, state)`. |
| `engine/presets.py` | `Preset` protocol + concrete presets `BeatPulse`, `HandFollow`, `SpinChase`. Bind events to effects. |
| `engine/engine.py` | 60 Hz frame loop. Drains the bus, dispatches events to presets, composites with channel-max blend. |
| `inputs/base.py` | `InputSource` protocol + `PushSource` base. New sources implement these and emit on the bus. |
| `inputs/{audio_beat,cv_hands,manual}.py` | Push-source bridges receiving events from the WS. |
| `inputs/cv_orin_stub.py` | Scaffolded Orin Nano CV worker; same event contract as `cv_hands`. |
| `outputs/base.py` | `OutputSink` protocol. |
| `outputs/simulator.py` | Encodes `LedFrame` to binary; pushes to subscribed WS clients. |
| `wled/discovery.py` | mDNS browser for `_wled._tcp.local.` + manual-add fallback. |
| `wled/client.py` | HTTP client for WLED's JSON API (`/json/info`, `/json/state`). |
| `wled/live_ws.py` | WS subscriber to WLED's `/ws` live LED stream + binary frame decoder. |
| `wled/calibration.py` | Pixel-range → bar binding model + JSON persistence. |
| `wled/mirror.py` | Bridges WLED live frames into the engine via `push_external_frame`. |
| `server/{app,api,ws,state}.py` | FastAPI factory + REST endpoints + WS bridge + assembled app state. |
| `storage/layout_store.py` | JSON persistence for `StageLayout`. |
| `cli.py` | `dj-lights serve` Click entry. |

### Frontend (`frontend/src/`)

| Module | Responsibility |
|---|---|
| `types.ts` | Mirrors backend types over the wire. |
| `transport/frames.ts` | Decodes binary `LedFrame` packets. |
| `transport/bridge.ts` | Auto-reconnecting WS for combined frames-out / events-in. |
| `transport/api.ts` | REST client for layouts and presets. |
| `state/store.ts` | Zero-dep typed pub/sub. |
| `stage/geometry.ts` | Stage <-> screen math; bar endpoints, hit testing, segment centres. |
| `stage/StageDesigner.ts` | 2D top-down editor: drag to move, shift+drag to rotate, lit segments overlay. |
| `stage/StagePreview.ts` | Strip-style live preview. |
| `presets/PresetPanel.ts` | Arm/disarm UI. |
| `wled/WledPanel.ts` | Discovery list + calibration table + mirror toggle. |
| `transport/wledApi.ts` | REST client for `/api/wled/*`. |
| `inputs/audio.ts` | Web Audio energy-onset beat detector (standalone-mode). |
| `inputs/handTracker.ts` | MediaPipe Hands → `hand_position` events. |
| `inputs/spinWheel.ts` | Drag wheel → `spin` events. |
| `app.ts` | Top-level wiring. |

## Wire formats

### `LedFrame` (server -> client, binary, big-endian)

```
u16   layout_version
u16   bar_count
f64   timestamp_ms
repeat bar_count:
    u8    bar_id_len
    bytes bar_id (utf-8)
    u16   pixel_count
    bytes pixels (3 * pixel_count, R G B)
```

### `Event` (client -> server, JSON)

```json
{ "kind": "<kind>", "timestamp_ms": <number>, "payload": { ... } }
```

Kinds + payload shapes are listed in `engine/events.py`.

## Why these boundaries

- **Inputs and outputs are protocols, not concrete classes.** The engine never
  imports a concrete source or sink; future sources (e.g. an Orin CNN, a MIDI
  clock, an Ableton Link bridge) and sinks (DMX, sACN, recording) plug in
  without changes to the core.
- **Presets are the authoring unit.** A preset = trigger kind(s) + effect +
  target group + params. The POC uses Python classes; a YAML/JSON DSL can
  replace that without touching effects or events.
- **Frames are immutable.** They flow from engine -> sinks -> wire without
  ever being mutated, eliminating a whole class of races and aliasing bugs.
- **The simulator is a first-class sink.** It is not a debug-only path; it
  shares the contract with the future hardware sink, so anything that works
  in the simulator works the same way over the wire.
