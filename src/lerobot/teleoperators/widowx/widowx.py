#!/usr/bin/env python

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

from lerobot.motors import Motor, MotorCalibration, MotorNormMode
from lerobot.motors.dynamixel import (
    DriveMode,
    DynamixelMotorsBus,
    OperatingMode,
)
from lerobot.utils.errors import DeviceAlreadyConnectedError, DeviceNotConnectedError

from ..teleoperator import Teleoperator
from .config_widowx import WidowXConfig

logger = logging.getLogger(__name__)


class WidowX(Teleoperator):
    """
    [WidowX](https://www.trossenrobotics.com/widowx-250) developed by Trossen Robotics
    """

    config_class = WidowXConfig
    name = "widowx"

    def __init__(self, config: WidowXConfig):
        super().__init__(config)
        self.config = config
        # Pass existing calibration (if any) so is_calibrated check is meaningful
        self.bus = DynamixelMotorsBus(
            port=self.config.port,
            motors={
                "waist": Motor(1, "xm430-w350", MotorNormMode.RANGE_M100_100),
                "shoulder": Motor(2, "xm430-w350", MotorNormMode.RANGE_M100_100),
                "shoulder_shadow": Motor(3, "xm430-w350", MotorNormMode.RANGE_M100_100),
                "elbow": Motor(4, "xm430-w350", MotorNormMode.RANGE_M100_100),
                "elbow_shadow": Motor(5, "xm430-w350", MotorNormMode.RANGE_M100_100),
                "forearm_roll": Motor(6, "xm430-w350", MotorNormMode.RANGE_M100_100),
                "wrist_angle": Motor(7, "xm430-w350", MotorNormMode.RANGE_M100_100),
                "wrist_rotate": Motor(8, "xl430-w250", MotorNormMode.RANGE_M100_100),
                "gripper": Motor(9, "xc430-w150", MotorNormMode.RANGE_0_100),
            },
            calibration=self.calibration,
        )

    @property
    def action_features(self) -> dict[str, type]:
        return {f"{motor}.pos": float for motor in self.bus.motors}

    @property
    def feedback_features(self) -> dict[str, type]:
        return {}

    @property
    def is_connected(self) -> bool:
        return self.bus.is_connected

    def connect(self, calibrate: bool = True):
        if self.is_connected:
            raise DeviceAlreadyConnectedError(f"{self} already connected")

        self.bus.connect()
        if not self.is_calibrated and calibrate:
            self.calibrate()

        self.configure()
        logger.info(f"{self} connected.")

    @property
    def is_calibrated(self) -> bool:
        return self.bus.is_calibrated

    def calibrate(self) -> None:
        self.bus.disable_torque()
        if self.calibration:
            # Calibration file exists, ask user whether to use it or run new calibration
            user_input = input(
                f"Press ENTER to use provided calibration file associated with the id {self.id}, or type 'c' and press ENTER to run calibration: "
            )
            if user_input.strip().lower() != "c":
                logger.info(f"Writing calibration file associated with the id {self.id} to the motors")
                self.bus.write_calibration(self.calibration)
                return

        logger.info(f"\nRunning calibration of {self}")
        # Use extended position during calibration for all except gripper
        for motor in self.bus.motors:
            self.bus.write("Operating_Mode", motor, OperatingMode.EXTENDED_POSITION.value)

        # Leader (WidowX) acts as the neutral source of truth. All drive modes are non-inverted.
        # The follower is responsible for adapting to its own mechanical differences.
        drive_modes = {}
        for motor in self.bus.motors:
            self.bus.write("Drive_Mode", motor, DriveMode.NON_INVERTED.value)
            drive_modes[motor] = DriveMode.NON_INVERTED.value


        input(f"Move {self} to the middle of its range of motion and press ENTER....")
        homing_offsets = self.bus.set_half_turn_homings()

        # Motors allowed continuous range (0..4095) during calibration: base yaw and wrist rotation
        full_turn_motors = ["waist", "wrist_rotate", "forearm_roll"]
        unknown_range_motors = [motor for motor in self.bus.motors if motor not in full_turn_motors]
        print(
            f"Move all joints except {full_turn_motors} sequentially through their "
            "entire ranges of motion.\nRecording positions. Press ENTER to stop..."
        )
        range_mins, range_maxes = self.bus.record_ranges_of_motion(unknown_range_motors)
        for motor in full_turn_motors:
            range_mins[motor] = 0
            range_maxes[motor] = 4095

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
        self.bus.disable_torque()
        self.bus.configure_motors()

        # Set secondary/shadow ID for shoulder and elbow. These joints have two motors.
        # As a result, if only one of them is required to move to a certain position,
        # the other will follow. This is to avoid breaking the motors.
        self.bus.write("Secondary_ID", "shoulder_shadow", 2)
        self.bus.write("Secondary_ID", "elbow_shadow", 4)

    def get_action(self) -> dict[str, float]:
        if not self.is_connected:
            raise DeviceNotConnectedError(f"{self} is not connected.")

        start = time.perf_counter()
        action = self.bus.sync_read("Present_Position")
        action = {f"{motor}.pos": val for motor, val in action.items()}
        dt_ms = (time.perf_counter() - start) * 1e3
        logger.debug(f"{self} read action: {dt_ms:.1f}ms")
        return action

    def send_feedback(self, feedback: dict[str, float]) -> None:
        raise NotImplementedError

    def disconnect(self) -> None:
        if not self.is_connected:
            raise DeviceNotConnectedError(f"{self} is not connected.")

        self.bus.disconnect()
        logger.info(f"{self} disconnected.")
