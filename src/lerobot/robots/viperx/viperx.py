# Copyright 2024 The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import time
from functools import cached_property
from typing import Any

from lerobot.cameras.utils import make_cameras_from_configs
from lerobot.motors import Motor, MotorCalibration, MotorNormMode
from lerobot.motors.dynamixel import (
    DynamixelMotorsBus,
    OperatingMode,
    DriveMode,
)
from lerobot.utils.constants import OBS_STATE
from lerobot.utils.errors import DeviceAlreadyConnectedError, DeviceNotConnectedError

from ..robot import Robot
from ..utils import ensure_safe_goal_position
from .config_viperx import ViperXConfig

logger = logging.getLogger(__name__)


class ViperX(Robot):
    """
    [ViperX](https://www.trossenrobotics.com/viperx-300) developed by Trossen Robotics
    """

    config_class = ViperXConfig
    name = "viperx"

    def __init__(
        self,
        config: ViperXConfig,
    ):
        super().__init__(config)
        self.config = config
        self.bus = DynamixelMotorsBus(
            port=self.config.port,
            motors={
                "waist": Motor(1, "xm540-w270", MotorNormMode.RANGE_M100_100),
                "shoulder": Motor(2, "xm540-w270", MotorNormMode.RANGE_M100_100),
                "shoulder_shadow": Motor(3, "xm540-w270", MotorNormMode.RANGE_M100_100),
                "elbow": Motor(4, "xm540-w270", MotorNormMode.RANGE_M100_100),
                "elbow_shadow": Motor(5, "xm540-w270", MotorNormMode.RANGE_M100_100),
                "forearm_roll": Motor(6, "xm540-w270", MotorNormMode.RANGE_M100_100),
                "wrist_angle": Motor(7, "xm540-w270", MotorNormMode.RANGE_M100_100),
                "wrist_rotate": Motor(8, "xm430-w350", MotorNormMode.RANGE_M100_100),
                "gripper": Motor(9, "xm430-w350", MotorNormMode.RANGE_0_100),
            },
            calibration=self.calibration,
        )
        self.cameras = make_cameras_from_configs(config.cameras)

    @property
    def _motors_ft(self) -> dict[str, type]:
        return {f"{motor}.pos": float for motor in self.bus.motors}

    @property
    def _cameras_ft(self) -> dict[str, tuple]:
        return {
            cam: (self.config.cameras[cam].height, self.config.cameras[cam].width, 3) for cam in self.cameras
        }

    @cached_property
    def observation_features(self) -> dict[str, type | tuple]:
        return {**self._motors_ft, **self._cameras_ft}

    @cached_property
    def action_features(self) -> dict[str, type]:
        return self._motors_ft

    @property
    def is_connected(self) -> bool:
        return self.bus.is_connected and all(cam.is_connected for cam in self.cameras.values())

    def connect(self, calibrate: bool = True) -> None:
        """
        We assume that at connection time, arm is in a rest position,
        and torque can be safely disabled to run calibration.
        """
        if self.is_connected:
            raise DeviceAlreadyConnectedError(f"{self} already connected")

        self.bus.connect()
        if not self.is_calibrated and calibrate:
            self.calibrate()

        for cam in self.cameras.values():
            cam.connect()

        self.configure()
        logger.info(f"{self} connected.")

    @property
    def is_calibrated(self) -> bool:
        return self.bus.is_calibrated

    def calibrate(self) -> None:
        self.bus.disable_torque()
        if self.calibration:
            user_input = input(
                f"Press ENTER to use provided calibration file associated with the id {self.id}, or type 'c' and press ENTER to run calibration: "
            )
            if user_input.strip().lower() != "c":
                logger.info(f"Writing calibration file associated with the id {self.id} to the motors")
                self.bus.write_calibration(self.calibration)
                return

        logger.info(f"\nRunning calibration of {self}")
        # Put all (except gripper) in extended position mode for safe full-range exploration
        for motor in self.bus.motors:
            self.bus.write("Operating_Mode", motor, OperatingMode.EXTENDED_POSITION.value)

        # To compensate for the ViperX's outward-facing motors compared to the WidowX's inward-facing ones,
        # we invert the primary shoulder and elbow motors.
        primary_inverted_joints = ["shoulder", "elbow"]

        # The shadow motors are mechanically coupled. To ensure they assist rather than oppose the primary
        # motors, they must have the opposite Drive_Mode. Because the primaries are inverted, the shadows
        # must be non-inverted.
        drive_modes = {}
        for motor in self.bus.motors:
            if motor in primary_inverted_joints:
                # Invert primary motors to match leader's world-frame motion
                self.bus.write("Drive_Mode", motor, DriveMode.INVERTED.value)
                drive_modes[motor] = DriveMode.INVERTED.value
            else:
                # All other motors, including the crucial shadow motors, should be non-inverted.
                self.bus.write("Drive_Mode", motor, DriveMode.NON_INVERTED.value)
                drive_modes[motor] = DriveMode.NON_INVERTED.value

        input("Move robot to the middle of its range of motion and press ENTER....")
        homing_offsets = self.bus.set_half_turn_homings()

        full_turn_motors = ["waist", "wrist_rotate", "forearm_roll"]
        unknown_range_motors = [motor for motor in self.bus.motors if motor not in full_turn_motors]
        print(
            f"Move all joints except {full_turn_motors} sequentially through their entire "
            "ranges of motion.\nRecording positions. Press ENTER to stop..."
        )
        range_mins, range_maxes = self.bus.record_ranges_of_motion(unknown_range_motors)
        for motor in full_turn_motors:
            range_mins[motor] = 0
            range_maxes[motor] = 4095
        for motor in unknown_range_motors:
            range_mins[motor] = max(0, range_mins[motor])
            range_maxes[motor] = min(4095, range_maxes[motor])

        self.calibration = {}
        for motor, m in self.bus.motors.items():
            self.calibration[motor] = MotorCalibration(
                id=m.id,
                drive_mode=drive_modes[motor],
                homing_offset=homing_offsets[motor],
                range_min=range_mins[motor],
                range_max=range_maxes[motor],
            )

        self.bus.write_calibration(self.calibration)
        self._save_calibration()
        logger.info(f"Calibration saved to {self.calibration_fpath}")

    def configure(self) -> None:
        with self.bus.torque_disabled():
            self.bus.configure_motors()

            # Set secondary/shadow ID for shoulder and elbow. These joints have two motors.
            # As a result, if only one of them is required to move to a certain position,
            # the other will follow. This is to avoid breaking the motors.
            self.bus.write("Secondary_ID", "shoulder_shadow", 2)
            self.bus.write("Secondary_ID", "elbow_shadow", 4)

            # Set a velocity limit of 131 as advised by Trossen Robotics
            # TODO(aliberts): remove as it's actually useless in position control
            # self.bus.write("Velocity_Limit", 131)

            # Use 'extended position mode' for all motors except gripper, because in joint mode the servos
            # can't rotate more than 360 degrees (from 0 to 4095) And some mistake can happen while assembling
            # the arm, you could end up with a servo with a position 0 or 4095 at a crucial point.
            # See: https://emanual.robotis.com/docs/en/dxl/x/x_series/#operating-mode11
            for motor in self.bus.motors:
                if motor != "gripper":
                    self.bus.write("Operating_Mode", motor, OperatingMode.EXTENDED_POSITION.value)

            # Use 'position control current based' for follower gripper to be limited by the limit of the
            # current. It can grasp an object without forcing too much even tho, it's goal position is a
            # complete grasp (both gripper fingers are ordered to join and reach a touch).
            self.bus.write("Operating_Mode", "gripper", OperatingMode.CURRENT_POSITION.value)

            # We intentionally DO NOT overwrite Drive_Mode here; calibration already stored all zeros
            # for follower. Leaving this untouched ensures hardware-level alignment with leader.

    def get_observation(self) -> dict[str, Any]:
        """The returned observations do not have a batch dimension."""
        if not self.is_connected:
            raise DeviceNotConnectedError(f"{self} is not connected.")

        obs_dict = {}

        # Read arm position
        # start = time.perf_counter()
        # obs_dict[OBS_STATE] = self.bus.sync_read("Present_Position")
        # obs_dict = {f"{motor}.pos": val for motor, val in obs_dict.items()}
        # dt_ms = (time.perf_counter() - start) * 1e3
        # logger.debug(f"{self} read state: {dt_ms:.1f}ms")


        start = time.perf_counter()
        motor_pos = self.bus.sync_read("Present_Position")
        obs_dict.update({f"{motor}.pos": val for motor, val in motor_pos.items()})
        dt_ms = (time.perf_counter() - start) * 1e3
        logger.debug(f"{self} read state: {dt_ms:.1f}ms")


        # Capture images from cameras
        for cam_key, cam in self.cameras.items():
            start = time.perf_counter()
            obs_dict[cam_key] = cam.async_read()
            dt_ms = (time.perf_counter() - start) * 1e3
            logger.debug(f"{self} read {cam_key}: {dt_ms:.1f}ms")

        return obs_dict

    def send_action(self, action: dict[str, float]) -> dict[str, float]:
        """Command arm to move to a target joint configuration.

        The relative action magnitude may be clipped depending on the configuration parameter
        `max_relative_target`. In this case, the action sent differs from original action.
        Thus, this function always returns the action actually sent.

        Args:
            action (dict[str, float]): The goal positions for the motors.

        Returns:
            dict[str, float]: The action sent to the motors, potentially clipped.
        """
        if not self.is_connected:
            raise DeviceNotConnectedError(f"{self} is not connected.")

        # No software mirroring: physical drive_mode differences between leader & follower
        # already achieve consistent Cartesian motion.

        # Only command primary joints; shadow motors follow via Secondary_ID.
        allowed_motors = {
            "waist",
            "shoulder",
            "elbow",
            "forearm_roll",
            "wrist_angle",
            "wrist_rotate",
            "gripper",
        }
        goal_pos = {
            key.removesuffix(".pos"): val
            for key, val in action.items()
            if key.endswith(".pos") and key.removesuffix(".pos") in allowed_motors
        }

        # Cap goal position when too far away from present position.
        # /!\ Slower fps expected due to reading from the follower.
        if self.config.max_relative_target is not None:
            present_pos = self.bus.sync_read("Present_Position")
            goal_present_pos = {key: (g_pos, present_pos[key]) for key, g_pos in goal_pos.items()}
            goal_pos = ensure_safe_goal_position(goal_present_pos, self.config.max_relative_target)

        # Send goal position to the arm
        self.bus.sync_write("Goal_Position", goal_pos)
        # Return the full original action (including shadows) for dataset compatibility.
        # Shadows are recorded as commanded, even though not sent (they follow via Secondary_ID).
        return action

    def disconnect(self):
        if not self.is_connected:
            raise DeviceNotConnectedError(f"{self} is not connected.")

        self.bus.disconnect(self.config.disable_torque_on_disconnect)
        for cam in self.cameras.values():
            cam.disconnect()

        logger.info(f"{self} disconnected.")
