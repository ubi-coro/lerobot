# backend/config_models.py
from typing import Literal, Optional, Dict
from pydantic import BaseModel, Field
from pathlib import Path

class CameraCfg(BaseModel):
    type: Literal["intelrealsense", "opencv", "reachy2"] = "intelrealsense"
    serial_number_or_name: str
    width: int = 640
    height: int = 480
    fps: int = 30

class RobotArmCfg(BaseModel):
    port: str
    id: str
    calibration_dir: Optional[Path] = None

class RobotCfg(BaseModel):
    type: Literal["viperx", "bi_viperx"] = "viperx"
    id: str
    left_arm: Optional[RobotArmCfg] = None
    right_arm: Optional[RobotArmCfg] = None
    port: Optional[str] = None  # für single-arm
    cameras: Dict[str, CameraCfg] = Field(default_factory=dict)
    calibration_dir: Optional[Path] = None  # Fallback für single-arm

class TeleopArmCfg(BaseModel):
    port: str
    id: str
    calibration_dir: Optional[Path] = None

class TeleopCfg(BaseModel):
    type: Literal["widowx", "bi_widowx"] = "widowx"
    id: str
    left_arm: Optional[TeleopArmCfg] = None
    right_arm: Optional[TeleopArmCfg] = None
    port: Optional[str] = None  # für single-arm
    calibration_dir: Optional[Path] = None  # Fallback für single-arm

class TeleopRequest(BaseModel):
    operation_mode: Literal["bimanual", "right", "left"] = "right"
    display_data: bool = False
    fps: int = 30
    robot_type: Literal["viperx", "bi_viperx"] = "viperx"
    teleop_type: Literal["widowx", "bi_widowx"] = "widowx"
    cameras_enabled: bool = True
    profile_name: Optional[str] = None
    config_version: str = "0.3.4"