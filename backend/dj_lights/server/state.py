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
from ..wled.calibration import CalibrationStore
from ..wled.discovery import WledDiscovery, WledRegistry
from ..wled.mirror import WledMirror


@dataclass
class AppState:
    bus: EventBus
    engine: Engine
    store: LayoutStore
    calibration_store: CalibrationStore
    wled_registry: WledRegistry
    wled_discovery: WledDiscovery
    layout_name: str
    presets: dict[str, Preset] = field(default_factory=dict)
    sources: dict[str, PushSource] = field(default_factory=dict)
    engine_task: asyncio.Task[None] | None = None
    wled_mirror: WledMirror | None = None

    @classmethod
    def build(cls, *, data_dir: Path, layout_name: str = "sample-5bar") -> AppState:
        bus = EventBus()
        store = LayoutStore(data_dir / "layouts")
        calibration_store = CalibrationStore(data_dir / "calibration")
        layout = store.load(layout_name)
        engine = Engine(layout=layout, bus=bus)
        registry = WledRegistry()
        return cls(
            bus=bus,
            engine=engine,
            store=store,
            calibration_store=calibration_store,
            wled_registry=registry,
            wled_discovery=WledDiscovery(registry),
            layout_name=layout_name,
            presets=default_preset_registry(),
            sources={
                "manual": ManualSource("manual", bus),
                "audio": AudioBeatSource("audio", bus),
                "cv-hands": CvHandsSource("cv-hands", bus),
            },
        )
