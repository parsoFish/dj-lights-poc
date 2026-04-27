from dj_lights.wled.discovery import WledNode, WledRegistry, manual_node


def test_registry_dedupes_by_id() -> None:
    reg = WledRegistry()
    a = WledNode(id="wled-A1", name="back", host="10.0.0.5")
    b = WledNode(id="wled-A1", name="back-renamed", host="10.0.0.5")
    reg.add(a)
    reg.add(b)
    assert len(reg.all()) == 1
    assert reg.get("wled-A1") is not None
    assert reg.get("wled-A1").name == "back-renamed"


def test_registry_lists_alphabetically() -> None:
    reg = WledRegistry()
    reg.add(WledNode(id="wled-Z", name="Zeta", host="10.0.0.10"))
    reg.add(WledNode(id="wled-A", name="alpha", host="10.0.0.5"))
    reg.add(WledNode(id="wled-B", name="Beta", host="10.0.0.6"))
    names = [n.name for n in reg.all()]
    assert names == ["alpha", "Beta", "Zeta"]


def test_registry_remove_idempotent() -> None:
    reg = WledRegistry()
    reg.add(WledNode(id="x", name="x", host="10.0.0.1"))
    reg.remove("x")
    reg.remove("x")
    assert reg.all() == []


def test_node_url_helpers() -> None:
    n = WledNode(id="x", name="x", host="10.0.0.1", port=80)
    assert n.http_base == "http://10.0.0.1:80"
    assert n.ws_url == "ws://10.0.0.1:80/ws"


def test_manual_node_factory_picks_id_and_source() -> None:
    n = manual_node("192.168.1.42")
    assert n.source == "manual"
    assert n.id == "manual:192.168.1.42:80"
    assert n.name == "192.168.1.42"

    named = manual_node("192.168.1.42", name="Front Bars", port=8080)
    assert named.id == "manual:192.168.1.42:8080"
    assert named.name == "Front Bars"
