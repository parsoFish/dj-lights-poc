import pytest

from dj_lights.engine.events import Event, EventBus
from dj_lights.inputs.audio_beat import AudioBeatSource
from dj_lights.inputs.cv_hands import CvHandsSource
from dj_lights.inputs.cv_orin_stub import OrinHandsSource
from dj_lights.inputs.manual import ManualSource


@pytest.mark.asyncio
async def test_push_sources_emit_to_bus() -> None:
    bus = EventBus()
    q = bus.subscribe()
    src = ManualSource("manual", bus)
    await src.publish(Event(kind="manual", timestamp_ms=0.0, payload={"action": "trigger"}))
    ev = await q.get()
    assert ev.kind == "manual"


@pytest.mark.asyncio
async def test_audio_and_cv_push_sources() -> None:
    bus = EventBus()
    q = bus.subscribe()
    audio = AudioBeatSource("a", bus)
    cv = CvHandsSource("c", bus)
    await audio.publish(Event(kind="beat", timestamp_ms=0.0, payload={"bpm": 120}))
    await cv.publish(Event(kind="hand_position", timestamp_ms=0.0, payload={"x": 0.5, "y": 0.5}))
    kinds = {(await q.get()).kind for _ in range(2)}
    assert kinds == {"beat", "hand_position"}


@pytest.mark.asyncio
async def test_orin_stub_raises() -> None:
    bus = EventBus()
    src = OrinHandsSource(bus)
    with pytest.raises(NotImplementedError):
        async for _ in src.stream():
            break
