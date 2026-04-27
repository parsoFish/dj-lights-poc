"""Output sink contract.

Sinks receive every frame the engine produces. Multiple sinks can be active
at once (e.g. simulator + real bars + recording), and the engine never has to
know what they do with the frame.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..engine.frame import LedFrame


@runtime_checkable
class OutputSink(Protocol):
    name: str

    async def write(self, frame: LedFrame) -> None:  # pragma: no cover - protocol
        ...
