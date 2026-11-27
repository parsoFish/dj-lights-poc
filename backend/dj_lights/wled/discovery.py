"""mDNS browser for ``_wled._tcp.local.`` plus manual-add fallback.

WLED nodes advertise themselves as ``_wled._tcp`` on the local network. A
short browse window typically picks up every powered-on board on the LAN.
Anything that doesn't show up (different VLAN, mDNS blocked) can be added
manually with an IP address — same shape goes into the registry.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from zeroconf import IPVersion, ServiceStateChange
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo, AsyncZeroconf

if TYPE_CHECKING:
    from zeroconf import Zeroconf

logger = logging.getLogger(__name__)

WLED_SERVICE_TYPE = "_wled._tcp.local."


@dataclass(frozen=True, slots=True)
class WledNode:
    """A discovered (or manually-added) WLED endpoint.

    ``id`` is stable across restarts: the ``mac`` from ``/json/info`` if we
    have it, otherwise ``host:port``.
    """

    id: str
    name: str
    host: str
    port: int = 80
    source: str = "mdns"  # mdns | manual

    @property
    def http_base(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def ws_url(self) -> str:
        return f"ws://{self.host}:{self.port}/ws"


@dataclass
class WledRegistry:
    """In-process store of known WLED nodes; deduplicated by ``id``."""

    _nodes: dict[str, WledNode] = field(default_factory=dict)

    def add(self, node: WledNode) -> None:
        self._nodes[node.id] = node

    def remove(self, node_id: str) -> None:
        self._nodes.pop(node_id, None)

    def get(self, node_id: str) -> WledNode | None:
        return self._nodes.get(node_id)

    def all(self) -> list[WledNode]:
        return sorted(self._nodes.values(), key=lambda n: n.name.lower())


class WledDiscovery:
    """Async mDNS browser for WLED nodes.

    Use as a context manager from FastAPI's lifespan; while active it
    populates the supplied registry as nodes appear and disappear on the LAN.
    """

    def __init__(self, registry: WledRegistry) -> None:
        self._registry = registry
        self._zc: AsyncZeroconf | None = None
        self._browser: AsyncServiceBrowser | None = None
        self._tasks: set[asyncio.Task[None]] = set()

    async def start(self) -> None:
        if self._zc is not None:
            return
        self._zc = AsyncZeroconf(ip_version=IPVersion.V4Only)
        self._browser = AsyncServiceBrowser(
            self._zc.zeroconf,
            [WLED_SERVICE_TYPE],
            handlers=[self._on_state_change],
        )

    async def stop(self) -> None:
        if self._browser is not None:
            await self._browser.async_cancel()
            self._browser = None
        if self._zc is not None:
            await self._zc.async_close()
            self._zc = None

    def _on_state_change(
        self,
        zeroconf: Zeroconf,
        service_type: str,
        name: str,
        state_change: ServiceStateChange,
    ) -> None:
        if state_change is ServiceStateChange.Removed:
            self._registry.remove(_node_id_from_service_name(name))
            return
        task = asyncio.ensure_future(self._resolve(zeroconf, service_type, name))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _resolve(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        info = AsyncServiceInfo(service_type, name)
        if not await info.async_request(zeroconf, 3000):
            return
        addrs = info.parsed_scoped_addresses() if hasattr(info, "parsed_scoped_addresses") else []
        if not addrs:
            ips = info.parsed_addresses() if hasattr(info, "parsed_addresses") else []
            addrs = list(ips)
        if not addrs:
            return
        host = addrs[0]
        node = WledNode(
            id=_node_id_from_service_name(name),
            name=name.replace(f".{WLED_SERVICE_TYPE}", "").rstrip("."),
            host=host,
            port=info.port or 80,
            source="mdns",
        )
        self._registry.add(node)
        logger.info("discovered WLED %s at %s:%d", node.name, node.host, node.port)


def _node_id_from_service_name(service_name: str) -> str:
    """Use the bare service hostname as the node id (e.g. 'wled-A1B2C3')."""

    return service_name.replace(f".{WLED_SERVICE_TYPE}", "").rstrip(".")


def manual_node(host: str, *, name: str | None = None, port: int = 80) -> WledNode:
    """Register a WLED node by IP/hostname when mDNS isn't available."""

    return WledNode(
        id=f"manual:{host}:{port}",
        name=name or host,
        host=host,
        port=port,
        source="manual",
    )
