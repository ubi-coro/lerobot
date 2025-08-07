import time
from collections import defaultdict
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence

import numpy as np

from lerobot.common.robot_devices.motors.dynamixel import DynamixelMotorsBusConfig
from lerobot.common.robot_devices.robots.configs import ManipulatorRobotConfig
from lerobot.common.robot_devices.robots.manipulator import ManipulatorRobot


@dataclass
class GelloConfig(ManipulatorRobotConfig):
    robot_type: str = "ur"
    calibration_dir: Optional[str] = None

    def __post_init__(self):
        if self.calibration_dir is None:
            self.calibration_dir = f".cache/calibration/{self.type}"

    @property
    def type(self):
        return f"{self.robot_type}-gello"

class GelloLeader(AbstractContextManager):
    """
    Lightweight reader around `ManipulatorRobot`.
    It *only* connects to the leader arms and makes their joint angles
    (optionally offset-corrected) available via `get_joint_states()`.

    Parameters
    ----------
    leader_ports : dict[str, str]
        Maps arm names (e.g. `"left"`, `"right"`) to the serial/USB ports
        on which their Dynamixel bus lives.
    robot_type : str, default "aloha"
        Name of a predefined joint specification.  Add your own in
        `_DEFAULT_JOINT_SPEC` if you use a different leader robot.
    offsets : dict[str, dict[str, float]], optional
        Per-joint angle offsets **in degrees** that are *added* to the raw
        readings so the downstream robot/sim sees the correct zero.
        Structure must mirror the result structure, e.g.:

            {
                "left":  {"waist": 2.0, "elbow": -1.3},
                "right": {"waist": 1.5}
            }

    mock : bool, default False
        Passes straight through to `ManipulatorRobotConfig.mock` so you can
        unit-test without hardware.
    """

    # ---------------------------------------------------------------------
    # 1.  Built-in motor maps (index + model) for common leader robots.
    #     Extend at will.  Only *leader* specs are needed because we never
    #     instantiate follower arms.
    # ---------------------------------------------------------------------
    _DEFAULT_GELLO_SPEC: Mapping[str, Mapping[str, List]] = {
        "ur": {
            "shoulder_pan":  [1, "xl330-m288"],
            "shoulder_lift": [2, "xl330-m288"],
            "elbow":         [3, "xl330-m288"],
            "wrist_1":       [4, "xl330-m288"],
            "wrist_2":       [5, "xl330-m288"],
            "wrist_3":       [6, "xl330-m288"],
            "gripper":       [7, "xl330-m077"],
        },
    }

    # ---------------------------------------------------------------------
    def __init__(
        self,
        leader_ports: Dict[str, str],
        *,
        robot_type: str = "ur",
        offsets: Dict[str, Dict[str, float]] | None = None,
        mock: bool = False,
    ):
        if robot_type not in self._DEFAULT_GELLO_SPEC:
            raise ValueError(
                f"Unknown `robot_type='{robot_type}'`.  "
                "Add its motor specification to `_DEFAULT_JOINT_SPEC` first."
            )

        self._offsets: dict[str, dict[str, float]] = defaultdict(dict)
        if offsets:
            for arm, joint_map in offsets.items():
                self._offsets[arm].update(joint_map)

        # -----------------------------------------------------------------
        # Build leader-only config.  Follower arms & cameras are empty.
        # -----------------------------------------------------------------
        leader_arm_cfgs: dict[str, DynamixelMotorsBusConfig] = {}
        joint_spec = self._DEFAULT_GELLO_SPEC[robot_type]
        for arm_name, port in leader_ports.items():
            leader_arm_cfgs[arm_name] = DynamixelMotorsBusConfig(
                port=port,
                motors=joint_spec,
            )

        robot_cfg = GelloConfig(
            leader_arms=leader_arm_cfgs,
            follower_arms={},               # <-- nothing to control
            cameras={},
            mock=mock,
            max_relative_target=None,       # only reading, no safety limiter needed
            robot_type=robot_type
        )

        self._robot = ManipulatorRobot(robot_cfg)

    # ---------------------------------------------------------------------
    # 2.  Public API
    # ---------------------------------------------------------------------
    def get_joint_states(self) -> Dict[str, np.ndarray]:
        """
        Returns
        -------
        dict[str, dict[str, float]]
            Nested mapping **arm → {joint_name: angle_deg}**.
            Offsets are already applied.
        """
        states: dict[str, np.ndarray] = {}

        for arm_name, bus in self._robot.leader_arms.items():
            raw: np.ndarray = bus.read("Present_Position")  # degrees by design
            corrected = raw.astype(float).copy()

            # Apply per-joint offsets (if any)
            for idx, joint_name in enumerate(bus.motor_names):
                corrected[idx] += self._offsets[arm_name].get(joint_name, 0.0)

            states[arm_name] = corrected

        return states

    def connect(self) -> None:
        """Manually close the serial ports and cameras (if any)."""
        self._robot.connect()

    def disconnect(self) -> None:
        """Manually close the serial ports and cameras (if any)."""
        self._robot.disconnect()

    # ---------------------------------------------------------------------
    # 3.  House-keeping helpers: context-manager & destructor
    # ---------------------------------------------------------------------
    def __enter__(self):
        self.connect()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def __del__(self):
        # Only attempt clean-up if the user forgot to call `disconnect`.
        try:
            if getattr(self._robot, "is_connected", False):
                self._robot.disconnect()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    leader = GelloLeader(
        leader_ports={"main": "/dev/ttyUSB0"}
    )

    leader.connect()

    while True:
        print(leader.get_joint_states())
        time.sleep(0.1)


