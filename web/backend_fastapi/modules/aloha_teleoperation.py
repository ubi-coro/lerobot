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
    show_cameras: bool = Field(default=True, description="Show camera feeds")
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
        safety_limits=True,
        performance_monitoring=True
    ),
    PresetType.NORMAL: AlohaConfig(
        fps=30,
        max_relative_target=50.0,  # Increased from 25 to allow better control
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
    suitable for visualization (optimized for performance).
    
    Args:
        robot: The ALOHA robot instance
        
    Returns:
        Dictionary mapping joint names to radian values, or empty dict if extraction fails
    """
    try:
        # Get current observation from ALOHA robot
        observation = robot.capture_observation()
        
        joint_positions = {}
        
        # ALOHA observation structure - try different possible keys in order of preference
        possible_keys = [
            "observation.action",  # Most common format
            "action",              # Direct action
            "observation.state",   # State data
            "state",              # Direct state
        ]
        
        action_tensor = None
        found_key = None
        
        # Find the first available key with valid data
        for key in possible_keys:
            if key in observation:
                candidate = observation[key]
                # Check if it's a valid tensor/array with expected length
                if hasattr(candidate, '__len__') and len(candidate) >= 14:  # At least 14 values needed
                    action_tensor = candidate
                    found_key = key
                    break
        
        if action_tensor is not None:
            # Extract joint positions based on ALOHA configuration
            # ALOHA typically has: [left_arm_joints..., right_arm_joints...]
            # Each arm usually has 7 joints: [waist, shoulder, elbow, forearm_roll, wrist_pitch, wrist_roll, gripper]
            
            if len(action_tensor) >= 14:  # Minimum for bimanual (7+7)
                # Left arm (first 7 values)
                joint_positions["left_base_rotation"] = float(action_tensor[0])      # waist/base
                joint_positions["left_shoulder_pitch"] = float(action_tensor[1])     # shoulder
                joint_positions["left_elbow_pitch"] = float(action_tensor[2])        # elbow  
                joint_positions["left_forearm_roll"] = float(action_tensor[3])       # forearm_roll
                joint_positions["left_wrist_pitch"] = float(action_tensor[4])        # wrist_pitch
                joint_positions["left_wrist_roll"] = float(action_tensor[5])         # wrist_roll
                joint_positions["left_gripper"] = float(action_tensor[6])            # gripper
                
                # Right arm (next 7 values) - only if we have enough data
                if len(action_tensor) >= 14:
                    joint_positions["right_base_rotation"] = float(action_tensor[7])     # waist/base
                    joint_positions["right_shoulder_pitch"] = float(action_tensor[8])    # shoulder
                    joint_positions["right_elbow_pitch"] = float(action_tensor[9])       # elbow
                    joint_positions["right_forearm_roll"] = float(action_tensor[10])     # forearm_roll
                    joint_positions["right_wrist_pitch"] = float(action_tensor[11])      # wrist_pitch
                    joint_positions["right_wrist_roll"] = float(action_tensor[12])       # wrist_roll
                    joint_positions["right_gripper"] = float(action_tensor[13])          # gripper
                
                # Log success only once per session
                if not hasattr(get_joint_positions_from_aloha, '_logged_success'):
                    logger.info(f"Successfully extracting joint positions from key: {found_key}, tensor length: {len(action_tensor)}")
                    get_joint_positions_from_aloha._logged_success = True
                    
            else:
                # Log unexpected length only once per session
                if not hasattr(get_joint_positions_from_aloha, '_logged_length_warning'):
                    logger.warning(f"ALOHA action tensor from {found_key} has unexpected length: {len(action_tensor)}")
                    get_joint_positions_from_aloha._logged_length_warning = True
        else:
            # Log missing keys only once per session
            if not hasattr(get_joint_positions_from_aloha, '_logged_missing_keys'):
                logger.warning(f"No valid action/state tensor found in ALOHA observation. Available keys: {list(observation.keys())}")
                get_joint_positions_from_aloha._logged_missing_keys = True
                
        return joint_positions
        
    except Exception as e:
        # Only log errors occasionally to avoid spam
        if not hasattr(get_joint_positions_from_aloha, '_error_count'):
            get_joint_positions_from_aloha._error_count = 0
        get_joint_positions_from_aloha._error_count += 1
        
        if get_joint_positions_from_aloha._error_count <= 3 or get_joint_positions_from_aloha._error_count % 50 == 0:
            logger.error(f"Error getting ALOHA joint positions (#{get_joint_positions_from_aloha._error_count}): {e}")
        
        return {}  # Return empty dict instead of dummy data

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
        
        # Handle cameras based on config
        if not config.show_cameras:
            # Completely disable cameras for ALOHA when not needed
            robot_config.cameras = {}
            logger.info("🎥 Cameras disabled")
        else:
            logger.info("🎥 Cameras enabled")
            
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
        
        # Verify single-arm configuration was applied correctly
        if hasattr(robot, 'leader_arms') and hasattr(robot, 'follower_arms'):
            active_leader_arms = list(robot.leader_arms.keys()) if robot.leader_arms else []
            active_follower_arms = list(robot.follower_arms.keys()) if robot.follower_arms else []
            logger.info(f"Active leader arms: {active_leader_arms}")
            logger.info(f"Active follower arms: {active_follower_arms}")
            
            # Validate single-arm configuration
            if config.operation_mode == OperationMode.LEFT_ONLY:
                if "right" in active_leader_arms or "right" in active_follower_arms:
                    logger.error("❌ RIGHT ARM still active in LEFT-ONLY mode! Configuration failed!")
                    raise Exception("Single-arm configuration failed - right arm still active")
                else:
                    logger.info("✅ LEFT-ONLY mode confirmed - right arm disabled")
            elif config.operation_mode == OperationMode.RIGHT_ONLY:
                if "left" in active_leader_arms or "left" in active_follower_arms:
                    logger.error("❌ LEFT ARM still active in RIGHT-ONLY mode! Configuration failed!")
                    raise Exception("Single-arm configuration failed - left arm still active")
                else:
                    logger.info("✅ RIGHT-ONLY mode confirmed - left arm disabled")
            else:
                logger.info("✅ BIMANUAL mode - both arms active")
        
        logger.info("ALOHA robot connected successfully")
        
        # Teleoperation loop (optimized for performance)
        loop_count = 0
        last_fps_time = time.time()
        last_broadcast_time = 0
        # Reduce joint broadcast frequency to improve performance (10 FPS instead of 20)
        broadcast_interval = 1.0 / 10  # 10 FPS for joint updates
        joint_broadcast_count = 0  # Track failed broadcasts
        
        logger.info(f"Starting teleoperation loop with {config.operation_mode} mode at {config.fps} FPS")
        
        while not aloha_state["stop_event"].is_set():
            loop_start = time.time()
            
            try:
                # Perform teleoperation step (LeRobot's method)
                observation, action = robot.teleop_step(record_data=True)
                
            except Exception as e:
                logger.error(f"Teleoperation step failed: {e}")
                # Check if it's a communication error
                if "Interrupted system call" in str(e) or "communication" in str(e).lower():
                    logger.warning("Communication error detected, attempting to reconnect...")
                    try:
                        robot.disconnect()
                        time.sleep(0.5)  # Brief pause
                        robot.connect()
                        logger.info("Reconnection successful")
                        continue
                    except Exception as reconnect_error:
                        logger.error(f"Reconnection failed: {reconnect_error}")
                        break
                else:
                    # Non-communication error, stop teleoperation
                    logger.error("Non-recoverable error, stopping teleoperation")
                    break
            
            # Update performance metrics
            loop_count += 1
            current_time = time.time()
            
            if current_time - last_fps_time >= 1.0:
                aloha_state["performance_metrics"]["average_fps"] = loop_count
                aloha_state["performance_metrics"]["frames_processed"] += loop_count
                loop_count = 0
                last_fps_time = current_time
            
            # Broadcast joint positions (optimized for performance)
            if websocket_manager and (current_time - last_broadcast_time) >= broadcast_interval:
                try:
                    joint_positions = get_joint_positions_from_aloha(robot)
                    
                    # Only broadcast if we have valid joint data
                    if joint_positions:
                        joint_data = {
                            "type": "aloha_joint_update",
                            "joints": joint_positions,
                            "timestamp": current_time,
                            "fps": aloha_state["performance_metrics"]["average_fps"],
                            "operation_mode": config.operation_mode
                        }
                        
                        # Broadcast to connected clients
                        if hasattr(websocket_manager, 'broadcast_joint_data_sync'):
                            websocket_manager.broadcast_joint_data_sync(joint_data)
                        
                        aloha_state["performance_metrics"]["last_joint_update"] = current_time
                        joint_broadcast_count = 0  # Reset failed count on success
                    else:
                        joint_broadcast_count += 1
                        # Don't spam logs with joint failures
                        if joint_broadcast_count % 10 == 1:
                            logger.debug(f"Joint extraction failed {joint_broadcast_count} times")
                    
                    last_broadcast_time = current_time
                        
                except Exception as e:
                    joint_broadcast_count += 1
                    # Only log every 10th error to reduce spam
                    if joint_broadcast_count % 10 == 1:
                        logger.warning(f"Error broadcasting ALOHA joint data (#{joint_broadcast_count}): {e}")
                    last_broadcast_time = current_time
            
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
            config = ALOHA_PRESET_CONFIGURATIONS[request.preset].copy()
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
