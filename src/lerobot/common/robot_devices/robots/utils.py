"""
Shim for robots.utils: provide minimal stand-ins.
Extend with actual logic if still required by GUI/web backend.
"""
def get_arm_id(name: str) -> int:
    # Placeholder mapping
    return 0

def make_robot_from_config(config):
    # Placeholder; integrate real builder later
    return object()

def make_robot(*args, **kwargs):
    return make_robot_from_config(None)