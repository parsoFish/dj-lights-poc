"""Application-level singletons stitched together at startup."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from ..engine.engine import Engine
from ..engine.events import EventBus
from ..engine.presets import Preset, default_preset_registry
from ..inputs.audio_beat import AudioBeatSource
from ..inputs.base import PushSource
from ..inputs.cv_hands import CvHandsSource
from ..inputs.manual import ManualSource
from ..storage.layout_store import LayoutStore


@dataclass
class AppState:
    bus: EventBus
    engine: Engine
    store: LayoutStore
    presets: dict[str, Preset] = field(default_factory=dict)
    sources: dict[str, PushSource] = field(default_factory=dict)
    engine_task: asyncio.Task[None] | None = None

    @classmethod
    def build(cls, *, data_dir: Path, layout_name: str = "sample-5bar") -> AppState:
        bus = EventBus()
        store = LayoutStore(data_dir / "layouts")
        layout = store.load(layout_name)
        engine = Engine(layout=layout, bus=bus)
        return cls(
            bus=bus,
            engine=engine,
            store=store,
            presets=default_preset_registry(),
            sources={
                "manual": ManualSource("manual", bus),
                "audio": AudioBeatSource("audio", bus),
                "cv-hands": CvHandsSource("cv-hands", bus),
            },
        )
