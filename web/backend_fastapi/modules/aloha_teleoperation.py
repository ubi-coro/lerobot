"""
ALOHA Teleoperation Module
=========================

ALOHA-specific teleoperation implementation that combines:
- Your advanced preset system (Safe/Normal/Performance)
- LeLab-style direct hardware control for responsiveness
- LeRobot's ALOHA robot classes for proper hardware integration
- Real-time joint position broadcasting for visualization

This bridges the gap between your sophisticated web interface
and the hardware-specific needs of ALOHA teleoperation.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import logging
import asyncio
import time
import threading
import os
from enum import Enum
import json

# ALOHA-specific imports from LeRobot
from lerobot.common.robot_devices.robots.configs import AlohaRobotConfig
from lerobot.common.robot_devices.utils import RobotDeviceAlreadyConnectedError, RobotDeviceNotConnectedError
from lerobot.common.robot_devices.robots.utils import make_robot_from_config
from lerobot.common.robot_devices.control_utils import control_loop, ControlEvents
from lerobot.scripts.control_robot import _init_rerun
from lerobot.common.robot_devices.control_configs import TeleoperateControlConfig

logger = logging.getLogger(__name__)

# Helper function to get absolute calibration directory
def get_calibration_dir():
    """Get absolute path to ALOHA calibration directory"""
    # Get the project root (4 levels up from this file)
    current_file = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
    calibration_dir = os.path.join(project_root, ".cache", "calibration", "aloha_lemgo_tabea")
    return calibration_dir

# Create router
router = APIRouter(prefix="/api/aloha-teleoperation", tags=["aloha-teleoperation"])

# Enums for better type safety
class OperationMode(str, Enum):
    BIMANUAL = "bimanual"
    LEFT_ONLY = "left_only"
    RIGHT_ONLY = "right_only"

class PresetType(str, Enum):
    SAFE = "safe"
    NORMAL = "normal" 
    PERFORMANCE = "performance"

# Pydantic models
class ApiResponse(BaseModel):
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None

class AlohaConfig(BaseModel):
    """ALOHA-specific teleoperation configuration"""
    fps: int = Field(default=30, ge=1, le=120, description="Frames per second")
    max_relative_target: Optional[float] = Field(default=25, ge=0, le=100, description="Maximum relative target (degrees)")
    moving_time: float = Field(default=0.1, ge=0.01, le=1.0, description="Moving time for velocity profiles")
    operation_mode: OperationMode = Field(default=OperationMode.BIMANUAL, description="Operation mode")
    show_cameras: bool = Field(default=True, description="Show camera feeds on web interface")
    display_data: bool = Field(default=False, description="Open LeRobot's external display window")
    safety_limits: bool = Field(default=True, description="Enable safety limits")
    performance_monitoring: bool = Field(default=True, description="Enable performance monitoring")
    calibration_dir: str = Field(default_factory=get_calibration_dir, description="Calibration directory")

class AlohaStartRequest(BaseModel):
    """Start ALOHA teleoperation request"""
    config: Optional[AlohaConfig] = None
    preset: Optional[PresetType] = None
    config_overrides: Optional[Dict[str, Any]] = None

# ALOHA Preset configurations (inspired by your system)
ALOHA_PRESET_CONFIGURATIONS = {
    PresetType.SAFE: AlohaConfig(
        fps=30,
        max_relative_target=5.0,  # Very conservative for safety
        moving_time=0.15,  # Slower movements
        operation_mode=OperationMode.BIMANUAL,
        show_cameras=True,
        display_data=False,  # Disabled by default for safety mode
        safety_limits=True,
        performance_monitoring=True
    ),
    PresetType.NORMAL: AlohaConfig(
        fps=30,
        max_relative_target=50.0,  # Increased from 25 to allow better control
        moving_time=0.1,  # Standard ALOHA timing
        operation_mode=OperationMode.BIMANUAL,
        show_cameras=True,
        display_data=False,  # Disabled by default
        safety_limits=True,
        performance_monitoring=True
    ),
    PresetType.PERFORMANCE: AlohaConfig(
        fps=60,
        max_relative_target=None,  # No limits - advanced users only
        moving_time=0.05,  # Faster response
        operation_mode=OperationMode.BIMANUAL,
        show_cameras=False,  # Disabled for performance
        display_data=True,   # Use external display for better performance
        safety_limits=False,  # Advanced users only
        performance_monitoring=True
    )
}

# Global state for ALOHA teleoperation
aloha_state = {
    "active": False,
    "robot": None,
    "config": None,
    "start_time": None,
    "control_thread": None,
    "stop_event": threading.Event(),
    "performance_metrics": {
        "frames_processed": 0,
        "average_fps": 0.0,
        "latency_ms": 0.0,
        "last_joint_update": 0.0
    }
}

def create_aloha_robot_config(config: AlohaConfig) -> AlohaRobotConfig:
    """
    Create ALOHA robot configuration from our config model.
    Similar to LeLab's configuration approach but using LeRobot's ALOHA config.
    """
    try:
        logger.info(f"Creating ALOHA robot config for operation mode: {config.operation_mode}")
        
        # Create base ALOHA configuration
        robot_config = AlohaRobotConfig(
            calibration_dir=config.calibration_dir,
            max_relative_target=config.max_relative_target,
            moving_time=config.moving_time,
            mock=False  # Real hardware
        )

        # Force a hardware reset on the cameras to handle "Device or resource busy" errors.
        # This makes the GUI more robust if a previous process crashed or another module is connected.
        for cam_name in robot_config.cameras:
            if robot_config.cameras[cam_name] is not None:
                robot_config.cameras[cam_name].force_hardware_reset = True
        
        # CRITICAL: Apply operation mode overrides BEFORE robot creation
        # This must happen before the robot is instantiated
        original_leader_arms = robot_config.leader_arms.copy()
        original_follower_arms = robot_config.follower_arms.copy()
        
        if config.operation_mode == OperationMode.LEFT_ONLY:
            # Keep only left arm configurations
            robot_config.leader_arms = {k: v for k, v in original_leader_arms.items() if k == "left"}
            robot_config.follower_arms = {k: v for k, v in original_follower_arms.items() if k == "left"}
            logger.info(f"✅ LEFT-ONLY: Filtered arms from {list(original_leader_arms.keys())} to {list(robot_config.leader_arms.keys())}")
            
        elif config.operation_mode == OperationMode.RIGHT_ONLY:
            # Keep only right arm configurations  
            robot_config.leader_arms = {k: v for k, v in original_leader_arms.items() if k == "right"}
            robot_config.follower_arms = {k: v for k, v in original_follower_arms.items() if k == "right"}
            logger.info(f"✅ RIGHT-ONLY: Filtered arms from {list(original_leader_arms.keys())} to {list(robot_config.leader_arms.keys())}")
            
        else:
            # Bimanual - keep all arms
            logger.info(f"✅ BIMANUAL: Keeping all arms {list(robot_config.leader_arms.keys())}")
        
        # Handle cameras based on config.
        # If display_data is true, we need the cameras for the rerun window,
        # regardless of the show_cameras setting (which is for the web UI).
        if not config.show_cameras and not config.display_data:
            # Completely disable cameras for ALOHA when not needed
            robot_config.cameras = {}
            logger.info("🎥 Cameras disabled (show_cameras=False and display_data=False)")
        else:
            logger.info("🎥 Cameras enabled (show_cameras=True or display_data=True)")
            
        return robot_config
        
    except Exception as e:
        logger.error(f"Error creating ALOHA robot config: {e}")
        raise

def aloha_teleoperation_worker(config: AlohaConfig):
    """
    Worker thread for ALOHA teleoperation.
    This function now integrates with LeRobot's control_loop for proper functionality.
    """
    try:
        # 1. Create Robot Instance
        logger.info(f"Creating ALOHA robot config for operation mode: {config.operation_mode}")
        robot_config = create_aloha_robot_config(config)
        robot = make_robot_from_config(robot_config)
        robot.connect()
        logger.info("ALOHA robot connected successfully")

        # 2. Prepare for LeRobot's control_loop
        # Create a control config object that control_loop understands
        control_cfg = TeleoperateControlConfig(
            fps=config.fps,
            display_data=config.display_data,
        )

        # This is the key: We MUST initialize rerun here, just like control_robot.py does.
        # control_loop() only logs to an existing session, it does not create one.
        if control_cfg.display_data:
            logger.info("🖥️ display_data=true: Initializing LeRobot's rerun session...")
            # Using the same session name as the official script for consistency.
            _init_rerun(control_config=control_cfg, session_name="lerobot_control_loop_teleop")
            logger.info("✅ LeRobot rerun session initialized.")

        # Create a custom event object to allow stopping the loop from our API
        class StoppableControlEvents(ControlEvents):
            def update(self):
                super().update()
                if aloha_state["stop_event"].is_set():
                    self["exit_early"] = True

        events = StoppableControlEvents({"exit_early": False})

        # 3. Run LeRobot's main control loop
        logger.info(f"Starting teleoperation using LeRobot's control_loop with display_data={control_cfg.display_data}")
        control_loop(
            robot=robot,
            teleoperate=True,
            display_data=control_cfg.display_data,
            fps=control_cfg.fps,
            events=events,
        )

    except Exception as e:
        logger.error(f"Error in ALOHA teleoperation worker: {e}", exc_info=True)
    finally:
        if 'robot' in locals() and robot.is_connected:
            robot.disconnect()
        aloha_state["active"] = False
        aloha_state["stop_event"].clear()
        logger.info("ALOHA teleoperation worker stopped and cleaned up.")

@router.post("/start", response_model=ApiResponse)
async def start_aloha_teleoperation(request: AlohaStartRequest):
    """
    Start ALOHA teleoperation with advanced configuration options.
    
    Combines your preset system with ALOHA-specific hardware control.
    """
    try:
        if aloha_state["active"]:
            return ApiResponse(
                status="error",
                message="ALOHA teleoperation is already active"
            )
        
        logger.info("Starting ALOHA teleoperation with advanced configuration")
        
        # Determine configuration (your preset system)
        if request.preset:
            # Create a new instance from the preset dict to allow attribute modification
            preset_config = ALOHA_PRESET_CONFIGURATIONS[request.preset]
            config = AlohaConfig(**preset_config.dict())
            logger.info(f"Using ALOHA preset configuration: {request.preset}")
            
            # Apply config overrides from frontend
            if request.config_overrides:
                logger.info(f"Applying config overrides: {request.config_overrides}")
                for key, value in request.config_overrides.items():
                    if hasattr(config, key):
                        # Fix operation mode mapping from frontend to backend
                        if key == "operation_mode":
                            if value == "right_arm":
                                value = "right_only"
                            elif value == "left_arm":
                                value = "left_only" 
                            elif value == "bimanual":
                                value = "bimanual"
                            logger.info(f"Mapped operation_mode: {request.config_overrides[key]} -> {value}")
                        
                        setattr(config, key, value)
                        logger.info(f"Override applied: {key} = {value}")
                    else:
                        logger.warning(f"Unknown config override: {key}")
                        
        elif request.config:
            config = request.config
            logger.info("Using custom ALOHA configuration")
        else:
            # Default to normal preset
            config = ALOHA_PRESET_CONFIGURATIONS[PresetType.NORMAL]
            logger.info("Using default (normal) ALOHA configuration")
        
        # Validate configuration for ALOHA
        if config.max_relative_target and config.max_relative_target > 50:
            logger.warning("High relative target detected for ALOHA, enabling safety limits")
            config.safety_limits = True
        
        # Optimize FPS for single-arm operation to reduce lag
        if config.operation_mode in [OperationMode.LEFT_ONLY, OperationMode.RIGHT_ONLY]:
            if config.fps > 30:
                logger.info(f"Reducing FPS from {config.fps} to 30 for single-arm operation to improve performance")
                config.fps = 30
        
        # Start teleoperation
        aloha_state["active"] = True
        aloha_state["config"] = config.dict()
        aloha_state["start_time"] = time.time()
        aloha_state["stop_event"].clear()
        
        # Reset performance metrics
        aloha_state["performance_metrics"] = {
            "frames_processed": 0,
            "average_fps": 0.0,
            "latency_ms": 0.0,
            "last_joint_update": 0.0
        }
        
        # Start worker thread (LeLab-style threading)
        aloha_state["control_thread"] = threading.Thread(
            target=aloha_teleoperation_worker,
            args=(config,),
            daemon=True
        )
        aloha_state["control_thread"].start()
        
        logger.info(f"ALOHA teleoperation started with config: {config.dict()}")
        
        return ApiResponse(
            status="success",
            message="ALOHA teleoperation started successfully",
            data={
                "active": True,
                "configuration": config.dict(),
                "preset_used": request.preset,
                "start_time": aloha_state["start_time"],
                "operation_mode": config.operation_mode
            }
        )
        
    except Exception as e:
        aloha_state["active"] = False
        logger.error(f"Failed to start ALOHA teleoperation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start ALOHA teleoperation: {str(e)}"
        )

@router.post("/stop", response_model=ApiResponse)
async def stop_aloha_teleoperation():
    """
    Stop ALOHA teleoperation and return session summary.
    
    Graceful shutdown with performance metrics (your approach).
    """
    try:
        logger.info("Stopping ALOHA teleoperation")
        
        if not aloha_state["active"]:
            return ApiResponse(
                status="info",
                message="ALOHA teleoperation was not active",
                data={"active": False}
            )
        
        # Signal stop (LeLab-style)
        aloha_state["stop_event"].set()
        
        # Wait for thread to finish
        if aloha_state["control_thread"] and aloha_state["control_thread"].is_alive():
            aloha_state["control_thread"].join(timeout=5.0)
        
        # Calculate session duration
        session_duration = time.time() - aloha_state["start_time"] if aloha_state["start_time"] else 0
        
        # Prepare session summary (your approach)
        session_summary = {
            "duration_seconds": round(session_duration, 2),
            "performance_metrics": aloha_state["performance_metrics"].copy(),
            "configuration_used": aloha_state["config"],
            "robot_type": "ALOHA"
        }
        
        # Reset state
        aloha_state["config"] = None
        aloha_state["start_time"] = None
        aloha_state["control_thread"] = None
        aloha_state["active"] = False
        
        logger.info(f"ALOHA teleoperation stopped. Session duration: {session_duration:.2f}s")
        
        return ApiResponse(
            status="success",
            message="ALOHA teleoperation stopped successfully",
            data={
                "active": False,
                "session_summary": session_summary
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to stop ALOHA teleoperation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop ALOHA teleoperation: {str(e)}"
        )

@router.get("/status", response_model=ApiResponse)
async def get_aloha_status():
    """
    Get current ALOHA teleoperation status and real-time metrics.
    """
    try:
        # Update performance metrics if active
        if aloha_state["active"]:
            current_time = time.time()
            session_duration = current_time - aloha_state["start_time"]
            
        status_data = {
            "active": aloha_state["active"],
            "robot_type": "ALOHA",
            "configuration": aloha_state["config"],
            "performance_metrics": aloha_state["performance_metrics"],
            "session_duration": (
                time.time() - aloha_state["start_time"] 
                if aloha_state["start_time"] else 0
            ),
            "robot_connected": aloha_state["robot"] is not None,
            "display_data_active": aloha_state["config"].get("display_data", False) if aloha_state["config"] else False
        }
        
        return ApiResponse(
            status="success",
            message="ALOHA teleoperation status retrieved",
            data=status_data
        )
        
    except Exception as e:
        logger.error(f"Failed to get ALOHA status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get ALOHA status: {str(e)}"
        )

@router.get("/presets", response_model=ApiResponse)
async def get_aloha_presets():
    """
    Get available ALOHA configuration presets.
    """
    try:
        presets_info = {}
        for preset_name, config in ALOHA_PRESET_CONFIGURATIONS.items():
            presets_info[preset_name] = {
                "name": preset_name.title(),
                "description": _get_aloha_preset_description(preset_name),
                "configuration": config.dict(),
                "robot_type": "ALOHA"
            }
        
        return ApiResponse(
            status="success",
            message="Available ALOHA presets retrieved",
            data={"presets": presets_info}
        )
        
    except Exception as e:
        logger.error(f"Failed to get ALOHA presets: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get ALOHA presets: {str(e)}"
        )

def _get_aloha_preset_description(preset: PresetType) -> str:
    """Get description for an ALOHA preset configuration"""
    descriptions = {
        PresetType.SAFE: "Safe mode optimized for ALOHA with conservative limits and full safety features",
        PresetType.NORMAL: "Balanced ALOHA performance with standard safety features enabled", 
        PresetType.PERFORMANCE: "High-performance ALOHA mode for experienced users with minimal safety limits"
    }
    return descriptions.get(preset, "Custom ALOHA configuration")
