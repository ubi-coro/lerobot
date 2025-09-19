"""
Shim utils forwarding to legacy or providing placeholders.
Populate with actual exceptions/utilities you rely on.
"""
try:
    from lerobot.robot_devices_legacy.utils import *  # type: ignore  # If you create one later
except Exception:
    # Minimal placeholder exceptions used by calling code
    class RobotDeviceAlreadyConnectedError(Exception):
        pass
    class RobotDeviceNotConnectedError(Exception):
        pass
    def busy_wait(seconds: float):
        import time
        time.sleep(seconds)
    def safe_disconnect(device):
        try:
            device.stop()
        except Exception:
            pass