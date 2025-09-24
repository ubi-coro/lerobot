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
import json
import os
from pathlib import Path
from enum import Enum

# ALOHA-specific imports from LeRobot
from lerobot.utils.robot_utils import busy_wait
from lerobot.utils.utils import init_logging
# Optional visualization dependency (rerun). Provide no-op fallbacks if unavailable.
try:  # pragma: no cover - optional dependency guard
    import rerun as rr  # type: ignore
    from lerobot.utils.visualization_utils import _init_rerun, log_rerun_data
    _RERUN_AVAILABLE = True
except Exception:
    _RERUN_AVAILABLE = False
    def _init_rerun(*args, **kwargs):
        return None
    def log_rerun_data(*args, **kwargs):
        return None
import shared
from . import camera_streaming
from . import robot as robot_module
from . import camera_streaming

# LeRobot imports are deferred to runtime inside functions to tolerate environments
# where optional dependencies (e.g., draccus) are not installed. This keeps the
# backend bootable so the GUI can load and the user can still access non-teleop APIs.

logger = logging.getLogger(__name__)

# Helper function to get absolute calibration directory
def get_calibration_dir():
    """Get absolute path to ALOHA calibration directory"""
    # Get the project root (4 levels up from this file)
    current_file = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
    calibration_dir = os.path.join(project_root, ".cache", "calibration", "aloha_lemgo_tabea")
    return calibration_dir

def load_hardware_config():
    """Load hardware configuration from ~/.config/lerobot/hardware_config.json"""
    config_path = Path.home() / ".config" / "lerobot" / "hardware_config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Hardware config not found at {config_path}. Please create it with your workstation's hardware settings.")
    with open(config_path, 'r') as f:
        return json.load(f)

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

def create_aloha_configs(config: AlohaConfig):
    """
    Create robot and teleoperator configs for ALOHA using new LeRobot factories.
    Loads hardware settings from config file.
    Supports bimanual, left_only, and right_only modes.
    """
    try:
        logger.info(f"Creating ALOHA configs for operation mode: {config.operation_mode}")
        
        # Load hardware config
        hardware_config = load_hardware_config()

        # Lazy import LeRobot factories and configs
        try:
            from lerobot.robots.utils import make_robot_from_config  # noqa: F401
            from lerobot.teleoperators.utils import make_teleoperator_from_config  # noqa: F401
            from lerobot.robots.bi_viperx.config_bi_viperx import BiViperXConfig
            from lerobot.teleoperators.bi_widowx.config_bi_widowx import BiWidowXConfig
            from lerobot.robots.viperx.config_viperx import ViperXConfig
            from lerobot.teleoperators.widowx.config_widowx import WidowXConfig
        except Exception as dep_err:
            raise RuntimeError(
                "LeRobot hardware dependencies are not available. "
                "Install the project with the appropriate extras (e.g., `pip install -e .[all]` or at least motors/robots extras) "
                f"to enable teleoperation. Details: {dep_err}"
            )
        
        if config.operation_mode == OperationMode.BIMANUAL:
            # Use bimanual configs
            robot_config = BiViperXConfig(
                id=hardware_config.get("follower_id"),
                left_arm_port=hardware_config["ports"]["follower_left"],
                right_arm_port=hardware_config["ports"]["follower_right"],
                left_arm_max_relative_target=hardware_config.get("max_relative_target", config.max_relative_target or 25),
                right_arm_max_relative_target=hardware_config.get("max_relative_target", config.max_relative_target or 25),
                cameras=hardware_config.get("cameras", {})
            )
            teleop_config = BiWidowXConfig(
                id=hardware_config.get("leader_id"),
                left_arm_port=hardware_config["ports"]["leader_left"],
                right_arm_port=hardware_config["ports"]["leader_right"],
                calibration_dir=Path(hardware_config.get("calibration_dir", get_calibration_dir())),
            )
            logger.info("BIMANUAL mode: using both arms with bi_widowx/bi_viperx")
            
        elif config.operation_mode == OperationMode.LEFT_ONLY:
            # Use single-arm configs for left arm
            robot_config = ViperXConfig(
                id=hardware_config.get("follower_left_id", hardware_config.get("follower_id")),
                port=hardware_config["ports"]["follower_left"],
                max_relative_target=hardware_config.get("max_relative_target", config.max_relative_target or 25),
                cameras=hardware_config.get("cameras", {})
            )
            teleop_config = WidowXConfig(
                id=hardware_config.get("leader_left_id", hardware_config.get("leader_id")),
                port=hardware_config["ports"]["leader_left"],
                calibration_dir=Path(hardware_config.get("calibration_dir", get_calibration_dir())),
            )
            logger.info("LEFT_ONLY mode: using left arm with widowx/viperx")
            
        elif config.operation_mode == OperationMode.RIGHT_ONLY:
            # Use single-arm configs for right arm
            robot_config = ViperXConfig(
                id=hardware_config.get("follower_right_id", hardware_config.get("follower_id")),
                port=hardware_config["ports"]["follower_right"],
                max_relative_target=hardware_config.get("max_relative_target", config.max_relative_target or 25),
                cameras=hardware_config.get("cameras", {})
            )
            teleop_config = WidowXConfig(
                id=hardware_config.get("leader_right_id", hardware_config.get("leader_id")),
                port=hardware_config["ports"]["leader_right"],
                calibration_dir=Path(hardware_config.get("calibration_dir", get_calibration_dir())),
            )
            logger.info("RIGHT_ONLY mode: using right arm with widowx/viperx")
        
        # Handle cameras
        if not config.show_cameras and not config.display_data:
            robot_config.cameras = {}
            logger.info("Cameras disabled")
        else:
            logger.info("Cameras enabled")
            
        return robot_config, teleop_config
        
    except Exception as e:
        logger.error(f"Error creating ALOHA configs: {e}")
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
            "teleop_connected": aloha_state.get("teleop") is not None,
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

def aloha_teleoperation_worker(config: AlohaConfig, reuse_existing: bool):
    """
    Worker thread for ALOHA teleoperation.
    This function now uses new LeRobot factories for robot and teleoperator.
    """
    try:
        # Lazy imports here too
        from lerobot.robots.utils import make_robot_from_config
        from lerobot.teleoperators.utils import make_teleoperator_from_config
        robot = None
        teleop = None
        if reuse_existing and aloha_state["robot"] is not None:
            robot = aloha_state["robot"]
            logger.info("Reusing already connected robot instance for teleoperation (no reconnection)")
            # Still create the teleoperator and connect it
            _, teleop_config = create_aloha_configs(config)
            teleop = make_teleoperator_from_config(teleop_config)
            teleop.connect(calibrate=False)
            aloha_state["teleop"] = teleop
            aloha_state["owned_robot"] = False
            logger.info("Teleoperator created and connected; robot reused from RobotService")
        else:
            # Create robot and teleoperator using new factories
            robot_config, teleop_config = create_aloha_configs(config)
            robot = make_robot_from_config(robot_config)
            teleop = make_teleoperator_from_config(teleop_config)
            
            # Connect them; avoid auto-calibration to prevent interactive prompts in GUI
            # Avoid auto-calibration to prevent interactive prompts during GUI sessions
            robot.connect(calibrate=False)
            teleop.connect(calibrate=False)
            
            aloha_state["robot"] = robot
            aloha_state["teleop"] = teleop
            aloha_state["owned_robot"] = True
            logger.info("Robot and teleoperator created and connected using new factories")

        # 2. Prepare for teleoperation loop
        # Initialize rerun if display_data is enabled
        if config.display_data and _RERUN_AVAILABLE:
            logger.info("🖥️ display_data=true: Initializing LeRobot's rerun session...")
            _init_rerun(session_name="lerobot_control_loop_teleop")
            logger.info("✅ LeRobot rerun session initialized.")

        # Start camera streams if requested
        try:
            if config.show_cameras:
                cam_fps = min(config.fps, 12)
                camera_streaming.start_streams(robot, fps=cam_fps)
                logger.info(f"Started camera streaming (fps={cam_fps})")
        except Exception as e:
            logger.warning(f"Failed to start camera streaming: {e}")

        # 3. Simple teleoperation loop (similar to teleoperate.py)
        aloha_state["stage"] = "running"
        logger.info(f"Starting teleoperation loop (fps={config.fps}, display_data={config.display_data})")
        loop_count = 0
        
        while not aloha_state["stop_event"].is_set():
            loop_start = time.perf_counter()
            
            # Get action from teleoperator
            action = teleop.get_action()
            
            # Get observation if displaying data
            if config.display_data:
                observation = robot.get_observation()
                log_rerun_data(observation, action)
            
            # Send action to robot
            robot.send_action(action)
            
            # Control timing
            dt_s = time.perf_counter() - loop_start
            busy_wait(1 / config.fps - dt_s)
            
            loop_s = time.perf_counter() - loop_start
            loop_count += 1
            
            # Update performance metrics
            try:
                pm = aloha_state.get("performance_metrics", {})
                prev_avg = float(pm.get("average_fps", 0.0) or 0.0)
                fps_inst = 1.0 / loop_s if loop_s > 0 else 0.0
                avg = (0.8 * prev_avg) + (0.2 * fps_inst)
                pm["average_fps"] = avg
                pm["frames_processed"] = float(pm.get("frames_processed", 0.0) or 0.0) + 1
                over_ms = max(0.0, (loop_s - (1 / config.fps)) * 1000.0)
                pm["latency_ms"] = over_ms
                pm["last_joint_update"] = time.time()
                aloha_state["performance_metrics"] = pm
            except Exception:
                pass

    except Exception as e:
        logger.error(f"Error in ALOHA teleoperation worker: {e}", exc_info=True)
    finally:
        aloha_state["stage"] = "stopping"
        # Stop camera streams before potentially disconnecting
        try:
            camera_streaming.stop_all_streams()
        except Exception as e:
            logger.debug(f"Error stopping camera streams: {e}")

        # Shutdown rerun if it was initialized
        if config.display_data and _RERUN_AVAILABLE:
            try:
                rr.rerun_shutdown()
            except Exception as e:
                logger.debug(f"Error shutting down rerun: {e}")

        if 'robot' in locals() and aloha_state.get("owned_robot") and robot.is_connected:
            try:
                robot.disconnect()
                logger.info("Disconnected owned robot instance after teleoperation")
            except Exception as e:
                logger.warning(f"Error disconnecting owned robot: {e}")
        if 'teleop' in locals() and aloha_state.get("owned_robot"):
            try:
                teleop.disconnect()
                logger.info("Disconnected owned teleoperator instance after teleoperation")
            except Exception as e:
                logger.warning(f"Error disconnecting owned teleoperator: {e}")
            logger.info("Leaving shared robot connected (owned by RobotService)")
        if aloha_state.get("owned_robot"):
            aloha_state["robot"] = None
            aloha_state["teleop"] = None
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
        
        # Determine reuse of existing robot_service robot, otherwise create new
        reuse_existing = False
        try:
            # Use the shared RobotService instance if available and connected
            if getattr(robot_module, "robot_service", None) and robot_module.robot_service.status.get("connected"):
                # If we don't already have a robot in teleop state, reuse robot_service.robot
                if not aloha_state.get("robot"):
                    aloha_state["robot"] = getattr(robot_module.robot_service, "robot", None)
                reuse_existing = aloha_state["robot"] is not None
                if reuse_existing:
                    logger.info("Shared RobotService robot detected; will reuse for teleoperation")
        except Exception:
            # Fallback to create new
            reuse_existing = False

        # Start teleoperation state
        aloha_state["active"] = True
        aloha_state["config"] = config.dict()
        aloha_state["start_time"] = time.time()
        aloha_state["stop_event"].clear()
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
            "teleop_connected": aloha_state.get("teleop") is not None,
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
