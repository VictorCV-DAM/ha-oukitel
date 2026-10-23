"""
Auto-reload trigger: when this file exists AND has changed,
the coordinator will detect it and reload the bridge callbacks.
This is written by the Antigravity agent to trigger a hot reload
without needing HA API access.
"""
RELOAD_TRIGGER = True
