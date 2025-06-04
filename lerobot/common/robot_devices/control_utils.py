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

########################################################################################
# Utilities
########################################################################################


import logging
import threading
import time
import traceback
from contextlib import nullcontext
from copy import copy
from functools import cache
from typing import Optional

import evdev
import numpy as np
import rerun as rr
import torch
from deepdiff import DeepDiff
from termcolor import colored

from lerobot.common.datasets.image_writer import safe_stop_image_writer
from lerobot.common.datasets.lerobot_dataset import LeRobotDataset
from lerobot.common.datasets.utils import get_features_from_robot
from lerobot.common.policies.pretrained import PreTrainedPolicy
from lerobot.common.robot_devices.motors.dynamixel import TorqueMode
from lerobot.common.robot_devices.robots.manipulator import ensure_safe_goal_position
from lerobot.common.robot_devices.robots.utils import Robot
from lerobot.common.robot_devices.utils import busy_wait
from lerobot.common.utils.utils import get_safe_torch_device, has_method


def log_control_info(robot: Robot, dt_s, episode_index=None, frame_index=None, fps=None):
    log_items = []
    if episode_index is not None:
        log_items.append(f"ep:{episode_index}")
    if frame_index is not None:
        log_items.append(f"frame:{frame_index}")

    def log_dt(shortname, dt_val_s):
        nonlocal log_items, fps
        info_str = f"{shortname}:{dt_val_s * 1000:5.2f} ({1 / dt_val_s:3.1f}hz)"
        if fps is not None:
            actual_fps = 1 / dt_val_s
            if actual_fps < fps - 1:
                info_str = colored(info_str, "yellow")
        log_items.append(info_str)

    # total step time displayed in milliseconds and its frequency
    log_dt("dt", dt_s)

    # TODO(aliberts): move robot-specific logs logic in robot.print_logs()
    if not robot.robot_type.startswith("stretch"):
        for name in robot.leader_arms:
            key = f"read_leader_{name}_pos_dt_s"
            if key in robot.logs:
                log_dt("dtRlead", robot.logs[key])

        for name in robot.follower_arms:
            key = f"write_follower_{name}_goal_pos_dt_s"
            if key in robot.logs:
                log_dt("dtWfoll", robot.logs[key])

            key = f"read_follower_{name}_pos_dt_s"
            if key in robot.logs:
                log_dt("dtRfoll", robot.logs[key])

        for name in robot.cameras:
            key = f"read_camera_{name}_dt_s"
            if key in robot.logs:
                log_dt(f"dtR{name}", robot.logs[key])

    info_str = " ".join(log_items)
    logging.info(info_str)


@cache
def is_headless():
    """Detects if python is running without a monitor."""
    try:
        import pynput  # noqa

        return False
    except Exception:
        print(
            "Error trying to import pynput. Switching to headless mode. "
            "As a result, the video stream from the cameras won't be shown, "
            "and you won't be able to change the control flow with keyboards. "
            "For more info, see traceback below.\n"
        )
        traceback.print_exc()
        print()
        return True


def predict_action(observation, policy, device, use_amp):
    observation = copy(observation)
    with (
        torch.inference_mode(),
        torch.autocast(device_type=device.type) if device.type == "cuda" and use_amp else nullcontext(),
    ):
        # Convert to pytorch format: channel first and float32 in [0,1] with batch dimension
        for name in observation:
            if "image" in name:
                observation[name] = observation[name].type(torch.float32) / 255
                observation[name] = observation[name].permute(2, 0, 1).contiguous()
            observation[name] = observation[name].unsqueeze(0)
            observation[name] = observation[name].to(device)

        # Compute the next action with the policy
        # based on the current observation
        action = policy.select_action(observation)

        # Remove batch dimension
        action = action.squeeze(0)

        # Move to cpu, if not already the case
        action = action.to("cpu", dtype=torch.float32)

    return action


class ControlEvents:
    def __init__(self, event_dict: dict, foot_switches: Optional[dict] = None):
        self._event_dict = copy(event_dict)
        self._foot_switch_threads = dict()

        for event_name in foot_switches:
            assert event_name in self._event_dict
            fs_params = foot_switches[event_name]
            self._foot_switch_threads[event_name] = FootSwitchHandler(
                device_path=f'/dev/input/event{fs_params["device"]}',
                toggle=bool(fs_params["toggle"]),
                event_name=event_name
            )
            self._foot_switch_threads[event_name].start()

    def __getitem__(self, key):
        assert key in self._event_dict
        return self._event_dict[key]

    def __setitem__(self, key, value):
        assert key in self._event_dict
        self._event_dict[key] = value

    def __len__(self):
        len(self._event_dict)

    def update(self):
        for handler in self._foot_switch_threads.values():
            self._event_dict.update(handler.keyboard_events)

    def stop(self):
        for handler in self._foot_switch_threads.values():
            handler.stop()

    def reset(self):
        self._event_dict = dict.fromkeys(self._event_dict, False)
        for handler in self._foot_switch_threads.values():
            handler.reset()


def init_keyboard_listener(foot_switches: Optional[dict] = None, interactive: bool = False):
    # Allow to exit early while recording an episode or resetting the environment,
    # by tapping the right arrow key '->'. This might require a sudo permission
    # to allow your terminal to monitor keyboard events.
    foot_switches = dict() if foot_switches is None else foot_switches
    if not interactive and "intervention" in foot_switches:
        del foot_switches["intervention"]

    events = ControlEvents({
        "exit_early": False,
        "rerecord_episode": False,
        "stop_recording": False,
        "intervention": False
    }, foot_switches=foot_switches)

    if is_headless():
        logging.warning(
            "Headless environment detected. On-screen cameras display and keyboard inputs will not be available."
        )
        listener = None
        return listener, events

    # Only import pynput if not in a headless environment
    from pynput import keyboard

    def on_press(key):
        try:
            if key == keyboard.Key.right:
                print("Right arrow key pressed. Exiting loop...")
                events["exit_early"] = True
            elif key == keyboard.Key.left:
                print("Left arrow key pressed. Exiting loop and rerecord the last episode...")
                events["rerecord_episode"] = True
                events["exit_early"] = True
            elif key == keyboard.Key.esc:
                print("Escape key pressed. Stopping data recording...")
                events["stop_recording"] = True
                events["exit_early"] = True
        except Exception as e:
            print(f"Error handling key press: {e}")

    listener = keyboard.Listener(on_press=on_press)
    listener.start()

    return listener, events


def warmup_record(
    robot,
    events,
    enable_teleoperation,
    warmup_time_s,
    display_data,
    fps,
):
    control_loop(
        robot=robot,
        control_time_s=warmup_time_s,
        display_data=display_data,
        events=events,
        fps=fps,
        teleoperate=enable_teleoperation,
    )


def record_episode(
    robot,
    dataset,
    events,
    episode_time_s,
    display_data,
    policy,
    fps,
    single_task,
):
    control_loop(
        robot=robot,
        control_time_s=episode_time_s,
        display_data=display_data,
        dataset=dataset,
        events=events,
        policy=policy,
        fps=fps,
        teleoperate=policy is None,
        single_task=single_task,
    )


@safe_stop_image_writer
def control_loop(
    robot,
    control_time_s: float | None = None,
    teleoperate: bool = False,
    interactive: bool = False,
    display_data: bool = False,
    dataset: LeRobotDataset | None = None,
    events=None,
    policy: PreTrainedPolicy = None,
    fps: int | None = None,
    single_task: str | None = None,
):
    # TODO(rcadene): Add option to record logs
    if not robot.is_connected:
        robot.connect()

    if events is None:
        events = ControlEvents({"exit_early": False})

    if control_time_s is None:
        control_time_s = float("inf")

    if teleoperate and policy is not None:
        raise ValueError("When `teleoperate` is True, `policy` should be None.")

    if interactive and policy is None:
        raise ValueError("When `dagger` is True, `policy` should not be None.")

    if dataset is not None and single_task is None:
        raise ValueError("You need to provide a task as argument in `single_task`.")

    if dataset is not None and fps is not None and dataset.fps != fps:
        raise ValueError(f"The dataset fps should be equal to requested fps ({dataset['fps']} != {fps}).")

    timestamp = 0
    start_episode_t = time.perf_counter()

    # Controls starts, if policy is given it needs cleaning up
    if policy is not None:
        policy.reset()

    while timestamp < control_time_s:
        start_loop_t = time.perf_counter()
        events.update()

        if teleoperate or events["intervention"]:
            if policy is not None:
                policy.reset()

            observation, action = teleop_step(robot)
        else:
            observation = robot.capture_observation()
            action = None
            observation["task"] = [single_task]
            observation["robot_type"] = [policy.robot_type] if hasattr(policy, "robot_type") else [""]
            if policy is not None:
                pred_action = predict_action(
                    observation, policy, get_safe_torch_device(policy.config.device), policy.config.use_amp
                )
                # Action can eventually be clipped using `max_relative_target`,
                # so action actually sent is saved in the dataset.
                action = robot.send_action(pred_action)
                action = {"action": action}

            # Send follower position to the leader
            if interactive:
                reverse_teleop_step(robot)

        # when interactive, only store frames if the human intervenes
        if dataset is not None and (not interactive or events["intervention"]):
            frame = {**observation, **action, "task": single_task}
            dataset.add_frame(frame)

        # TODO(Steven): This should be more general (for RemoteRobot instead of checking the name, but anyways it will change soon)
        if (display_data and not is_headless()) or (display_data and robot.robot_type.startswith("lekiwi")):
            if action is not None:
                for k, v in action.items():
                    for i, vv in enumerate(v):
                        rr.log(f"sent_{k}_{i}", rr.Scalar(vv.numpy()))

            image_keys = [key for key in observation if "image" in key]
            for key in image_keys:
                rr.log(key, rr.Image(observation[key].numpy()), static=True)

        if fps is not None:
            dt_s = time.perf_counter() - start_loop_t
            busy_wait(1 / fps - dt_s)

        dt_s = time.perf_counter() - start_loop_t
        log_control_info(robot, dt_s, fps=fps)

        timestamp = time.perf_counter() - start_episode_t
        if events["exit_early"]:
            events["exit_early"] = False
            break


def reset_environment(robot, events, reset_time_s, fps):
    # TODO(rcadene): refactor warmup_record and reset_environment
    busy_wait(1.0 / fps)

    if has_method(robot, "teleop_safety_stop"):
        robot.teleop_safety_stop()

    control_loop(
        robot=robot,
        control_time_s=reset_time_s,
        events=events,
        fps=fps,
        teleoperate=True,
    )


def stop_recording(robot, listener, display_data):
    robot.disconnect()

    if not is_headless() and listener is not None:
        listener.stop()


def sanity_check_dataset_name(repo_id, policy_cfg):
    _, dataset_name = repo_id.split("/")
    # either repo_id doesnt start with "eval_" and there is no policy
    # or repo_id starts with "eval_" and there is a policy

    # Check if dataset_name starts with "eval_" but policy is missing
    if dataset_name.startswith("eval_") and policy_cfg is None:
        raise ValueError(
            f"Your dataset name begins with 'eval_' ({dataset_name}), but no policy is provided ({policy_cfg.type})."
        )

    # Check if dataset_name does not start with "eval_" but policy is provided
    if not dataset_name.startswith("eval_") and policy_cfg is not None:
        raise ValueError(
            f"Your dataset name does not begin with 'eval_' ({dataset_name}), but a policy is provided ({policy_cfg.type})."
        )


def sanity_check_dataset_robot_compatibility(
    dataset: LeRobotDataset, robot: Robot, fps: int, use_videos: bool
) -> None:
    fields = [
        ("robot_type", dataset.meta.robot_type, robot.robot_type),
        ("fps", dataset.fps, fps),
        ("features", dataset.features, get_features_from_robot(robot, use_videos)),
    ]

    mismatches = []
    for field, dataset_value, present_value in fields:
        diff = DeepDiff(dataset_value, present_value, exclude_regex_paths=[r".*\['info'\]$"])
        if diff:
            mismatches.append(f"{field}: expected {present_value}, got {dataset_value}")

    if mismatches:
        raise ValueError(
            "Dataset metadata compatibility check failed with mismatches:\n" + "\n".join(mismatches)
        )



class FootSwitchHandler:
    def __init__(self, device_path="/dev/input/event18", event_name="episode_success", toggle: bool = False):
        self.device = evdev.InputDevice(device_path)
        self.keyboard_events = {event_name: False}
        self.toggle = toggle
        self.event_name = event_name
        self.running = True

    def start(self):
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()

    def _run(self):
        logging.info(f"Listening for foot switch events from {self.device.name} ({self.device.path})...")
        for event in self.device.read_loop():
            if not self.running:
                break
            if event.type == evdev.ecodes.EV_KEY:
                key_event = evdev.categorize(event)
                if key_event.keystate == 1:  # Key down
                    if self.toggle:
                        if self.keyboard_events[self.event_name]:
                            logging.info(f"Foot switch pressed again - {self.event_name} toggled OFF")
                            self.keyboard_events[self.event_name] = False
                        else:
                            logging.info(f"Foot switch pressed - {self.event_name} toggled ON")
                            self.keyboard_events[self.event_name] = True
                    else:
                        logging.info(f"Foot switch pressed - {self.event_name} ON")
                        self.keyboard_events[self.event_name]  = True
                elif key_event.keystate == 0 and not self.toggle:  # Key release
                    logging.info(f"Foot switch released - {self.event_name} OFF")
                    self.keyboard_events[self.event_name] = False

    def stop(self):
        self.running = False

    def reset(self):
        self.keyboard_events = {self.event_name: False}


def teleop_step(robot):
    for name in robot.follower_arms:
        if (robot.leader_arms[name].read("Torque_Enable") != TorqueMode.DISABLED.value).any():
            robot.leader_arms[name].write("Torque_Enable", TorqueMode.DISABLED.value)
    return robot.teleop_step(record_data=True)

def reverse_teleop_step(robot):
    for name in robot.follower_arms:
        if (robot.leader_arms[name].read("Torque_Enable") != TorqueMode.ENABLED.value).any():
            robot.leader_arms[name].write("Torque_Enable", TorqueMode.ENABLED.value)

        goal_pos = robot.follower_arms[name].read("Present_Position")

        # Cap goal position when too far away from present position.
        # Slower fps expected due to reading from the follower.
        if robot.config.max_relative_target is not None:
            present_pos = robot.leader_arms[name].read("Present_Position")

            # Convert goal_pos to tensor to match present_pos type
            goal_pos_tensor = torch.from_numpy(goal_pos)
            present_pos_tensor = torch.from_numpy(present_pos)

            # Now both are tensors for the ensure_safe_goal_position function
            goal_pos_tensor = ensure_safe_goal_position(
                goal_pos_tensor,
                present_pos_tensor,
                robot.config.max_relative_target
            )

            # Convert back to numpy for the write operation
            goal_pos = goal_pos_tensor.numpy()

        # Ensure the right data type
        goal_pos = goal_pos.astype(np.float32)

        robot.leader_arms[name].write("Goal_Position", goal_pos)


