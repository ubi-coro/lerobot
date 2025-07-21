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
from enum import Enum
import json

# ALOHA-specific imports from LeRobot
from lerobot.common.robot_devices.robots.configs import AlohaRobotConfig
from lerobot.common.robot_devices.utils import RobotDeviceAlreadyConnectedError, RobotDeviceNotConnectedError
from lerobot.common.robot_devices.robots.utils import make_robot_from_config

logger = logging.getLogger(__name__)

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
    show_cameras: bool = Field(default=True, description="Show camera feeds")
    safety_limits: bool = Field(default=True, description="Enable safety limits")
    performance_monitoring: bool = Field(default=True, description="Enable performance monitoring")
    calibration_dir: str = Field(default=".cache/calibration/aloha_lemgo_tabea", description="Calibration directory")

class AlohaStartRequest(BaseModel):
    """Start ALOHA teleoperation request"""
    config: Optional[AlohaConfig] = None
    preset: Optional[PresetType] = None

# ALOHA Preset configurations (inspired by your system)
ALOHA_PRESET_CONFIGURATIONS = {
    PresetType.SAFE: AlohaConfig(
        fps=30,
        max_relative_target=5.0,  # Very conservative for safety
        moving_time=0.15,  # Slower movements
        operation_mode=OperationMode.BIMANUAL,
        show_cameras=True,
        safety_limits=True,
        performance_monitoring=True
    ),
    PresetType.NORMAL: AlohaConfig(
        fps=30,
        max_relative_target=25.0,  # ALOHA default
        moving_time=0.1,  # Standard ALOHA timing
        operation_mode=OperationMode.BIMANUAL,
        show_cameras=True,
        safety_limits=True,
        performance_monitoring=True
    ),
    PresetType.PERFORMANCE: AlohaConfig(
        fps=60,
        max_relative_target=None,  # No limits - advanced users only
        moving_time=0.05,  # Faster response
        operation_mode=OperationMode.BIMANUAL,
        show_cameras=False,  # Disabled for performance
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
    "websocket_manager": None,
    "performance_metrics": {
        "frames_processed": 0,
        "average_fps": 0.0,
        "latency_ms": 0.0,
        "last_joint_update": 0.0
    }
}

def get_joint_positions_from_aloha(robot) -> Dict[str, float]:
    """
    Extract current joint positions from ALOHA robot and convert to a format
    suitable for visualization (similar to LeLab's approach).
    
    Args:
        robot: The ALOHA robot instance
        
    Returns:
        Dictionary mapping joint names to radian values
    """
    try:
        # Get current observation from ALOHA robot
        observation = robot.capture_observation()
        
        joint_positions = {}
        
        # ALOHA has left and right arms, each with multiple joints
        # Map ALOHA motor names to visualization joint names
        aloha_joint_mapping = {
            # Left arm
            "left_waist": "left_base_rotation",
            "left_shoulder": "left_shoulder_pitch", 
            "left_elbow": "left_elbow_pitch",
            "left_forearm_roll": "left_forearm_roll",
            "left_wrist_angle": "left_wrist_pitch",
            "left_wrist_rotate": "left_wrist_roll",
            "left_gripper": "left_gripper",
            
            # Right arm  
            "right_waist": "right_base_rotation",
            "right_shoulder": "right_shoulder_pitch",
            "right_elbow": "right_elbow_pitch", 
            "right_forearm_roll": "right_forearm_roll",
            "right_wrist_angle": "right_wrist_pitch",
            "right_wrist_rotate": "right_wrist_roll", 
            "right_gripper": "right_gripper"
        }
        
        # Extract joint positions from observation
        for motor_key, joint_name in aloha_joint_mapping.items():
            if motor_key in observation:
                # ALOHA positions are typically already in radians
                joint_positions[joint_name] = float(observation[motor_key])
            else:
                logger.warning(f"Motor {motor_key} not found in observation")
                joint_positions[joint_name] = 0.0
                
        return joint_positions
        
    except Exception as e:
        logger.error(f"Error getting ALOHA joint positions: {e}")
        # Return zero positions as fallback
        return {f"{arm}_{joint}": 0.0 
                for arm in ["left", "right"] 
                for joint in ["base_rotation", "shoulder_pitch", "elbow_pitch", 
                             "forearm_roll", "wrist_pitch", "wrist_roll", "gripper"]}

def create_aloha_robot_config(config: AlohaConfig) -> AlohaRobotConfig:
    """
    Create ALOHA robot configuration from our config model.
    Similar to LeLab's configuration approach but using LeRobot's ALOHA config.
    """
    try:
        # Create base ALOHA configuration
        robot_config = AlohaRobotConfig(
            calibration_dir=config.calibration_dir,
            max_relative_target=config.max_relative_target,
            moving_time=config.moving_time,
            mock=False  # Real hardware
        )
        
        # Apply operation mode overrides
        if config.operation_mode == OperationMode.LEFT_ONLY:
            # Disable right arm
            robot_config.leader_arms = {"left": robot_config.leader_arms["left"]}
            robot_config.follower_arms = {"left": robot_config.follower_arms["left"]}
        elif config.operation_mode == OperationMode.RIGHT_ONLY:
            # Disable left arm  
            robot_config.leader_arms = {"right": robot_config.leader_arms["right"]}
            robot_config.follower_arms = {"right": robot_config.follower_arms["right"]}
        # Bimanual uses both arms (default)
        
        # Handle cameras based on config
        if not config.show_cameras:
            robot_config.cameras = {}
            
        return robot_config
        
    except Exception as e:
        logger.error(f"Error creating ALOHA robot config: {e}")
        raise

def aloha_teleoperation_worker(config: AlohaConfig, websocket_manager=None):
    """
    ALOHA teleoperation worker thread.
    Combines LeLab's direct approach with your advanced monitoring.
    """
    try:
        logger.info("Starting ALOHA teleoperation worker")
        
        # Create and connect robot (similar to LeLab's approach)
        robot_config = create_aloha_robot_config(config)
        robot = make_robot_from_config(robot_config)
        
        logger.info("Connecting to ALOHA robot...")
        robot.connect()
        aloha_state["robot"] = robot
        
        logger.info("ALOHA robot connected successfully")
        
        # Teleoperation loop (inspired by LeLab but with your monitoring)
        loop_count = 0
        last_fps_time = time.time()
        last_broadcast_time = 0
        broadcast_interval = 1.0 / 20  # 20 FPS for joint updates
        
        while not aloha_state["stop_event"].is_set():
            loop_start = time.time()
            
            # Perform teleoperation step (LeRobot's method)
            observation, action = robot.teleop_step(record_data=True)
            
            # Update performance metrics
            loop_count += 1
            current_time = time.time()
            
            if current_time - last_fps_time >= 1.0:
                aloha_state["performance_metrics"]["average_fps"] = loop_count
                aloha_state["performance_metrics"]["frames_processed"] += loop_count
                loop_count = 0
                last_fps_time = current_time
            
            # Broadcast joint positions (LeLab-style real-time updates)
            if websocket_manager and (current_time - last_broadcast_time) >= broadcast_interval:
                try:
                    joint_positions = get_joint_positions_from_aloha(robot)
                    joint_data = {
                        "type": "aloha_joint_update",
                        "joints": joint_positions,
                        "timestamp": current_time,
                        "fps": aloha_state["performance_metrics"]["average_fps"]
                    }
                    
                    # Broadcast to connected clients
                    if hasattr(websocket_manager, 'broadcast_joint_data_sync'):
                        websocket_manager.broadcast_joint_data_sync(joint_data)
                    
                    aloha_state["performance_metrics"]["last_joint_update"] = current_time
                    last_broadcast_time = current_time
                    
                except Exception as e:
                    logger.error(f"Error broadcasting ALOHA joint data: {e}")
            
            # Calculate and limit loop timing
            loop_duration = time.time() - loop_start
            target_duration = 1.0 / config.fps
            
            if loop_duration < target_duration:
                time.sleep(target_duration - loop_duration)
            
            aloha_state["performance_metrics"]["latency_ms"] = loop_duration * 1000
            
        logger.info("ALOHA teleoperation loop ended")
        
    except Exception as e:
        logger.error(f"Error in ALOHA teleoperation worker: {e}")
        raise
    finally:
        # Clean disconnect (LeLab-style cleanup)
        if aloha_state["robot"]:
            try:
                aloha_state["robot"].disconnect()
                logger.info("ALOHA robot disconnected")
            except Exception as e:
                logger.warning(f"Error disconnecting ALOHA robot: {e}")
        
        aloha_state["robot"] = None
        aloha_state["active"] = False

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
            config = ALOHA_PRESET_CONFIGURATIONS[request.preset]
            logger.info(f"Using ALOHA preset configuration: {request.preset}")
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
            args=(config, aloha_state.get("websocket_manager")),
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
            "robot_connected": aloha_state["robot"] is not None
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

def set_websocket_manager(websocket_manager):
    """Set the WebSocket manager for real-time joint updates (LeLab-style)"""
    aloha_state["websocket_manager"] = websocket_manager
