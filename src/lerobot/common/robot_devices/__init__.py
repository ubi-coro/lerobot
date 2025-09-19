"""
COMPAT SHIM (TEMPORARY)
Re-exports legacy robot device modules from the new location
`lerobot.robot_devices_legacy.*` so existing imports keep working.

TODO: Remove this package after migrating all imports to:
    lerobot.robot_devices_legacy...
"""
from lerobot.robot_devices_legacy import *  # noqa: F401,F403