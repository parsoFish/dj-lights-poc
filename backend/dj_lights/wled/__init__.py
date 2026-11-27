"""WLED integration: mDNS discovery, HTTP info client, live WS subscriber.

The friend's lighting rig is driven by WLED firmware running on an ESP-32.
Phase 6 connects to it as a sidecar — read-only — so our stage designer can
mirror whatever LedFx (or any other source) is currently rendering on his
bars. No writes happen here; that arrives in Phase 7's override path.
"""
