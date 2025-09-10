"""FastAPI-native RobotService implementation (hardware capable).

This replaces the legacy Flask RobotService. It provides only the
functionality currently needed by the API layer:
  - connect_aloha(overrides)
  - disconnect()
  - status dict with keys: connected, available_arms, cameras, error, mode

If hardware connection fails, it returns connected=False with an error
message but does not raise (the API layer will surface the info).
"""

from __future__ import annotations
import logging, os, threading, time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from lerobot.common.robot_devices.robots.configs import AlohaRobotConfig
    from lerobot.common.robot_devices.robots.utils import make_robot_from_config
except Exception as e:  # pragma: no cover - dependency/import environment issues
    AlohaRobotConfig = None  # type: ignore
    make_robot_from_config = None  # type: ignore
    logger.warning(f"Robot dependencies not available: {e}")


class RobotService:
    def __init__(self, use_mock: bool = False, socketio=None):
        self.use_mock = use_mock
        self.socketio = socketio
        self.robot = None
        self.robot_cfg = None
        self.status: Dict[str, Any] = {
            "connected": False,
            "available_arms": [],
            "cameras": [],
            "error": None,
            "mode": None,
        }
        self._lock = threading.Lock()

    # --- Public API expected by modules.robot ---
    def connect_aloha(self, overrides: Optional[List[str]] = None) -> Dict[str, Any]:
        with self._lock:
            if self.status["connected"]:
                return {
                    "connected": True,
                    "already_connected": True,
                    "available_arms": self.status["available_arms"],
                    "cameras": self.status["cameras"],
                }

            if make_robot_from_config is None or AlohaRobotConfig is None:
                err = "LeRobot hardware packages not importable (check installation)."
                logger.error(err)
                self.status["error"] = err
                return {"connected": False, "error": err}

            try:
                project_root = self._find_project_root()
                # Allow override through environment variable LEROBOT_CALIB_DIR
                env_calib = os.getenv("LEROBOT_CALIB_DIR")
                if env_calib:
                    calibration_dir = env_calib
                    logger.info(f"Using calibration dir from LEROBOT_CALIB_DIR: {calibration_dir}")
                else:
                    calibration_dir = os.path.join(project_root, ".cache", "calibration", "aloha_lemgo_tabea")
                    logger.info(f"Using default calibration dir: {calibration_dir}")

                if not os.path.isdir(calibration_dir):
                    raise FileNotFoundError(
                        "Calibration directory not found: {} (set LEROBOT_CALIB_DIR to override)".format(calibration_dir)
                    )

                self.robot_cfg = AlohaRobotConfig(
                    calibration_dir=calibration_dir,
                    max_relative_target=25,
                    moving_time=0.1,
                    mock=self.use_mock,
                )

                # Apply simple overrides (only supports key=value or ~dict.key removal like legacy)
                if overrides:
                    for ov in overrides:
                        try:
                            if ov.startswith("~"):
                                key = ov[1:]
                                self._apply_exclusion_override(key)
                            elif "=" in ov:
                                k, v = ov.split("=", 1)
                                self._apply_value_override(k, v)
                        except Exception as oe:  # pragma: no cover - defensive
                            logger.warning(f"Override '{ov}' ignored: {oe}")

                self.robot = make_robot_from_config(self.robot_cfg)
                logger.info("Connecting to robot hardware (ALOHA)...")
                self.robot.connect()

                self.status["connected"] = True
                self.status["error"] = None
                self.status["available_arms"] = list(self.robot.leader_arms.keys()) + list(self.robot.follower_arms.keys())
                if getattr(self.robot, 'cameras', None):
                    self.status["cameras"] = [{"id": name, "name": name} for name in self.robot.cameras.keys()]
                else:
                    self.status["cameras"] = []

                logger.info(f"Robot connected with arms={self.status['available_arms']} cameras={len(self.status['cameras'])}")
                return {
                    "connected": True,
                    "available_arms": self.status["available_arms"],
                    "cameras": self.status["cameras"],
                }
            except Exception as e:
                logger.error(f"Hardware connection failed: {e}")
                self.status["connected"] = False
                self.status["error"] = str(e)
                return {"connected": False, "error": str(e)}

    def disconnect(self) -> None:
        with self._lock:
            try:
                if self.robot and getattr(self.robot, 'is_connected', False):
                    self.robot.disconnect()
            except Exception as e:  # pragma: no cover
                logger.warning(f"Robot disconnect issue: {e}")
            finally:
                self.status["connected"] = False
                self.status["mode"] = None

    # --- Helpers ---
    def _find_project_root(self) -> str:
        here = os.path.abspath(os.path.dirname(__file__))
        # ascend until we find pyproject.toml or git root fallback
        cur = here
        for _ in range(8):
            if os.path.isfile(os.path.join(cur, 'pyproject.toml')):
                return cur
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
        return os.path.abspath(os.path.join(here, "../../../.."))

    def _apply_exclusion_override(self, key: str):
        if not self.robot_cfg:
            return
        if "." in key:
            main_key, sub_key = key.split('.', 1)
            if hasattr(self.robot_cfg, main_key):
                attr = getattr(self.robot_cfg, main_key)
                if isinstance(attr, dict) and sub_key in attr:
                    del attr[sub_key]
                    logger.info(f"Excluded {key} via override")

    def _apply_value_override(self, key: str, value: str):
        if not self.robot_cfg:
            return
        target = self.robot_cfg
        if '.' in key:
            parts = key.split('.')
            for part in parts[:-1]:
                if hasattr(target, part):
                    target = getattr(target, part)
        final_key = key.split('.')[-1]
        if hasattr(target, final_key):
            current = getattr(target, final_key)
            try:
                if isinstance(current, bool):
                    cast_val = value.lower() == 'true'
                elif isinstance(current, int):
                    cast_val = int(value)
                elif isinstance(current, float):
                    cast_val = float(value)
                elif value == '{}':
                    cast_val = {}
                else:
                    cast_val = value
                setattr(target, final_key, cast_val)
                logger.info(f"Override applied {key}={cast_val}")
            except Exception as e:  # pragma: no cover
                logger.warning(f"Failed applying override {key}={value}: {e}")

__all__ = ["RobotService"]
