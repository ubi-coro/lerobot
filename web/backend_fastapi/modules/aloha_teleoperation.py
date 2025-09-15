"""
ALOHA Teleoperation Module
==========================

Thin FastAPI wrapper around LeRobot's ALOHA teleoperation primitives.

Removed legacy custom preset layer (SAFE / NORMAL / PERFORMANCE) to rely on
one canonical configuration object (AlohaConfig) with optional overrides
from the frontend. This keeps close alignment with upstream LeRobot while
retaining:
    * Operation mode mapping (bimanual / left_only / right_only)
    * Camera enable / disable logic
    * Threaded control loop with stop event
    * Basic safety guard (auto-enable safety_limits for extreme values)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging
import time
import threading
import os
from enum import Enum

# ALOHA-specific imports from LeRobot
from lerobot.common.robot_devices.robots.configs import AlohaRobotConfig
from lerobot.common.robot_devices.utils import RobotDeviceAlreadyConnectedError, RobotDeviceNotConnectedError
from lerobot.common.robot_devices.robots.utils import make_robot_from_config
from lerobot.common.robot_devices.control_utils import control_loop, ControlEvents
from . import camera_streaming
from lerobot.scripts.control_robot import _init_rerun
from lerobot.common.robot_devices.control_configs import TeleoperateControlConfig
import shared

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

class OperationMode(str, Enum):
    BIMANUAL = "bimanual"
    LEFT_ONLY = "left_only"
    RIGHT_ONLY = "right_only"

# Pydantic models
class ApiResponse(BaseModel):
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None

class AlohaConfig(BaseModel):
    """ALOHA-specific teleoperation configuration"""
    robot_type: str = Field(default="aloha", description="Robot type (currently only 'aloha' supported)")
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
    """Start ALOHA teleoperation request (single configuration path)."""
    # Accept loose dict so we can map legacy operation_mode strings (e.g. 'right_arm')
    config: Optional[Dict[str, Any]] = None

# Global state for ALOHA teleoperation
aloha_state = {
    "active": False,
    "robot": None,          # Robot instance in use for teleoperation
    "owned_robot": False,    # Whether this module created (and must disconnect) the robot
    "config": None,
    "start_time": None,
    "control_thread": None,
    "stop_event": threading.Event(),
    "events": None,          # ControlEvents instance (for immediate exit signaling)
    "stage": "idle",        # idle|initializing|running|stopping
    "performance_metrics": {
        "frames_processed": 0,
        "average_fps": 0.0,
        "latency_ms": 0.0,
        "last_joint_update": 0.0
    }
}

def _get_robot_service():
    """Dynamically retrieve RobotService instance from modules.robot.

    This avoids stale imports and mirrors the recorder's dynamic access pattern.
    If the service isn't initialized yet, attempt to initialize it.
    """
    try:
        from . import robot as robot_module  # type: ignore
        rs = getattr(robot_module, "robot_service", None)
        if rs is None:
            init = getattr(robot_module, "initialize_services", None)
            if callable(init):
                init()
                rs = getattr(robot_module, "robot_service", None)
        return rs
    except Exception:
        return None

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

    # Note: IntelRealSenseCameraConfig defaults force_hardware_reset=True.
    # We don't override it here so that reused camera instances aren't forced to reset again.
        
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


def get_teleoperation_status_snapshot() -> Dict[str, Any]:
    """Return a stable snapshot of current teleoperation state."""
    try:
        session_duration = time.time() - aloha_state["start_time"] if aloha_state.get("start_time") else 0
        cfg = aloha_state.get("config") or {}
        return {
            "active": bool(aloha_state.get("active")),
            "stage": aloha_state.get("stage"),
            "robot_type": "ALOHA",
            "configuration": cfg,
            "performance_metrics": aloha_state.get("performance_metrics", {}),
            "session_duration": session_duration,
            "robot_connected": aloha_state.get("robot") is not None,
            "owned_robot": bool(aloha_state.get("owned_robot")),
            "display_data_active": bool(cfg.get("display_data", False)) if isinstance(cfg, dict) else False,
        }
    except Exception as e:
        logger.debug(f"teleop status snapshot error: {e}")
        return {"active": False, "stage": "idle", "robot_type": "ALOHA", "session_duration": 0}


async def emit_teleoperation_status(room: str | None = None):
    """Emit teleoperation_status event via Socket.IO if available."""
    try:
        sio = shared.get_socketio()
        if not sio:
            return
        payload = get_teleoperation_status_snapshot()
        await sio.emit("teleoperation_status", payload, room=room)
    except Exception:
        logger.debug("teleoperation_status emit failed", exc_info=True)

def _build_robot_overrides_from_config(config: AlohaConfig) -> list[str]:
    """
    Map Aloha teleop config to RobotService.connect_aloha overrides so the
    robot is instantiated with the correct arms/cameras and motion params.

    Supported override patterns in RobotService:
      - key=value for scalar attrs (e.g., max_relative_target, moving_time, calibration_dir)
      - ~dict.key to remove entries from dicts (e.g., ~leader_arms.right)
      - cameras={} to disable all cameras cleanly
    """
    overrides: list[str] = []
    # Calibration dir (explicit, avoids relying on env var)
    if config.calibration_dir:
        overrides.append(f"calibration_dir={config.calibration_dir}")
    # Motion params
    if config.max_relative_target is not None:
        overrides.append(f"max_relative_target={int(config.max_relative_target)}")
    overrides.append(f"moving_time={float(config.moving_time)}")
    # Arm selection
    if config.operation_mode == OperationMode.LEFT_ONLY:
        overrides += ["~leader_arms.right", "~follower_arms.right"]
    elif config.operation_mode == OperationMode.RIGHT_ONLY:
        overrides += ["~leader_arms.left", "~follower_arms.left"]
    # Camera enable/disable: if neither UI streaming nor rerun is desired, drop cameras
    if not config.show_cameras and not config.display_data:
        overrides.append("cameras={}")
    return overrides


def aloha_teleoperation_worker(config: AlohaConfig, reuse_existing: bool):
    """
    Worker thread for ALOHA teleoperation.
    This function now integrates with LeRobot's control_loop for proper functionality.
    """
    try:
        if reuse_existing and aloha_state["robot"] is not None:
            robot = aloha_state["robot"]
            logger.info("Reusing already connected robot instance for teleoperation (no reconnection)")
        else:
            # Prefer centralized RobotService so teleop/recording share the same instance
            rs = _get_robot_service()
            if rs is not None:
                overrides = _build_robot_overrides_from_config(config)
                try:
                    logger.info(f"Requesting robot via RobotService with overrides: {overrides}")
                    result = rs.connect_aloha(overrides=overrides)
                    if not result.get("connected"):
                        raise RuntimeError(result.get("error") or "RobotService failed to connect")
                    robot = rs.robot
                    aloha_state["robot"] = robot
                    aloha_state["owned_robot"] = False
                    logger.info("Robot acquired via RobotService (shared instance)")
                except Exception as e:
                    logger.error(f"RobotService connection failed, falling back to direct creation: {e}")
                    # Fallback to direct creation (rare path)
                    robot_config = create_aloha_robot_config(config)
                    robot = make_robot_from_config(robot_config)
                    robot.connect()
                    aloha_state["robot"] = robot
                    aloha_state["owned_robot"] = True
                    logger.info("ALOHA robot connected successfully (direct instance)")
            else:
                # Legacy fallback if RobotService unavailable
                logger.warning("RobotService not available; creating robot directly (fallback)")
                robot_config = create_aloha_robot_config(config)
                robot = make_robot_from_config(robot_config)
                robot.connect()
                aloha_state["robot"] = robot
                aloha_state["owned_robot"] = True
                logger.info("ALOHA robot connected successfully (direct instance)")

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
        # Store events so stop endpoint can signal immediate exit
        aloha_state["events"] = events

        # Start camera streams if requested in config (treat show_cameras purely as streaming toggle)
        try:
            if config.show_cameras:
                # Default camera streaming fps: min(control loop fps, 12)
                cam_fps = min(config.fps, 12)
                try:
                    cam_keys = list(getattr(robot, 'cameras', {}).keys())
                    logger.info(f"Camera devices available on robot: {cam_keys}")
                except Exception:
                    logger.info("No robot.cameras introspection available")
                camera_streaming.start_streams(robot, fps=cam_fps)
                logger.info(f"Started camera streaming (fps={cam_fps}) for cameras: {camera_streaming.get_active_streams()}")
        except Exception as e:
            logger.warning(f"Failed to start camera streaming: {e}")

        # 3. Run LeRobot's main control loop in short segments to allow responsive stop
        aloha_state["stage"] = "running"
        logger.info(f"Starting segmented teleoperation loop (fps={control_cfg.fps}, display_data={control_cfg.display_data})")
        segment_seconds = 1.0  # run control loop in 1s segments
        while not aloha_state["stop_event"].is_set():
            control_loop(
                robot=robot,
                teleoperate=True,
                display_data=control_cfg.display_data,
                fps=control_cfg.fps,
                events=events,
                control_time_s=segment_seconds,
            )
            # Additional early exit if events flagged exit_early
            if events["exit_early"]:
                break

    except Exception as e:
        logger.error(f"Error in ALOHA teleoperation worker: {e}", exc_info=True)
    finally:
        aloha_state["stage"] = "stopping"
        # Stop camera streams before potentially disconnecting
        try:
            camera_streaming.stop_all_streams()
        except Exception as e:
            logger.debug(f"Error stopping camera streams: {e}")

        # Only disconnect hardware if we created it here
        if 'robot' in locals() and aloha_state.get("owned_robot") and robot.is_connected:
            try:
                robot.disconnect()
                logger.info("Disconnected owned robot instance after teleoperation")
            except Exception as e:
                logger.warning(f"Error disconnecting owned robot: {e}")
        if not aloha_state.get("owned_robot"):
            logger.info("Leaving shared robot connected (owned by RobotService)")
        if aloha_state.get("owned_robot"):
            aloha_state["robot"] = None
        aloha_state["owned_robot"] = False
        aloha_state["active"] = False
        aloha_state["stop_event"].clear()
        logger.info("ALOHA teleoperation worker stopped and cleaned up.")

@router.post("/start", response_model=ApiResponse)
async def start_aloha_teleoperation(request: AlohaStartRequest):
    """
    Start ALOHA teleoperation with a single unified configuration.
    Legacy preset layer removed: frontend passes an optional config dict.
    """
    try:
        if aloha_state["active"]:
            return ApiResponse(
                status="error",
                message="ALOHA teleoperation is already active"
            )
        
        logger.info("Starting ALOHA teleoperation (single-config mode)")

        # Build config object (apply mapping for legacy operation_mode values)
        if request.config:
            cfg_dict = {**request.config}
            if "operation_mode" in cfg_dict:
                original = cfg_dict["operation_mode"]
                if original == "right_arm":
                    cfg_dict["operation_mode"] = "right_only"
                elif original == "left_arm":
                    cfg_dict["operation_mode"] = "left_only"
                elif original == "bimanual":
                    cfg_dict["operation_mode"] = "bimanual"
                if original != cfg_dict["operation_mode"]:
                    logger.info(f"Mapped operation_mode: {original} -> {cfg_dict['operation_mode']}")
            config = AlohaConfig(**cfg_dict)
            logger.info("Using provided ALOHA configuration")
        else:
            config = AlohaConfig()
            logger.info("Using default ALOHA configuration")
        
        # Validate configuration for ALOHA
        if config.max_relative_target and config.max_relative_target > 50:
            logger.warning("High relative target detected for ALOHA, enabling safety limits")
            config.safety_limits = True
        
        # Optimize FPS for single-arm operation to reduce lag
        if config.operation_mode in [OperationMode.LEFT_ONLY, OperationMode.RIGHT_ONLY]:
            if config.fps > 30:
                logger.info(f"Reducing FPS from {config.fps} to 30 for single-arm operation to improve performance")
                config.fps = 30
        
        # Determine reuse of existing robot_service robot, otherwise acquire it via RobotService
        reuse_existing = False
        rs = _get_robot_service()
        if rs and getattr(rs, 'status', {}).get('connected') and getattr(rs, 'robot', None):
            aloha_state["robot"] = rs.robot
            aloha_state["owned_robot"] = False
            reuse_existing = True
            logger.info("Detected existing connected robot_service robot; will reuse for teleoperation")
        elif rs:
            # Try to connect via RobotService using config-derived overrides so we don't create a second instance elsewhere
            overrides = _build_robot_overrides_from_config(config)
            try:
                logger.info(f"No shared robot yet; connecting via RobotService with overrides: {overrides}")
                result = rs.connect_aloha(overrides=overrides)
                if not result.get("connected"):
                    raise RuntimeError(result.get("error") or "RobotService failed to connect")
                aloha_state["robot"] = rs.robot
                aloha_state["owned_robot"] = False
                reuse_existing = True
                logger.info("Robot connected via RobotService for teleoperation (shared instance)")
            except Exception as e:
                logger.error(f"RobotService connect failed; worker will fallback to direct creation: {e}")
                reuse_existing = False
        else:
            logger.info("RobotService unavailable; worker will create robot directly (fallback)")

        # Start teleoperation state
        aloha_state["active"] = True
        aloha_state["config"] = config.dict()
        aloha_state["start_time"] = time.time()
        aloha_state["stop_event"].clear()
        aloha_state["events"] = None  # will be set by worker once created
        aloha_state["stage"] = "initializing"

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
            args=(config, reuse_existing),
            daemon=True
        )
        aloha_state["control_thread"].start()

        # Emit status immediately after start
        try:
            await emit_teleoperation_status()
        except Exception:
            logger.debug("emit teleop status after start failed", exc_info=True)

        logger.info(f"ALOHA teleoperation started with config: {config.dict()}")

        return ApiResponse(
            status="success",
            message="ALOHA teleoperation started successfully",
            data={
                "active": True,
                "configuration": config.dict(),
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
        if aloha_state.get("events") is not None:
            # Directly request early exit
            try:
                aloha_state["events"]["exit_early"] = True
            except Exception:
                pass
        
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

        # Emit status after stop
        try:
            await emit_teleoperation_status()
        except Exception:
            logger.debug("emit teleop status after stop failed", exc_info=True)
        
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
            "stage": aloha_state.get("stage"),
            "robot_type": "ALOHA",
            "configuration": aloha_state["config"],
            "performance_metrics": aloha_state["performance_metrics"],
            "session_duration": (
                time.time() - aloha_state["start_time"] if aloha_state["start_time"] else 0
            ),
            "robot_connected": aloha_state["robot"] is not None,
            "owned_robot": aloha_state.get("owned_robot"),
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

# Preset endpoint removed: legacy custom presets deprecated.
