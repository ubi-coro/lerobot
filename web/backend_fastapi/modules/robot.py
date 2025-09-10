"""
Robot Connection and Hardware Management Module
==============================================

Handles robot connection, disconnection, and hardware-level operations.
Extracted from main.py for better organization.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
import sys
import os
import importlib

# Import shared state
import shared

# Attempt multiple import strategies for RobotService to ensure hardware path loads.
RobotService = None  # type: ignore
StreamService = None  # placeholder (not yet implemented)

_robot_import_attempts = [
    "backend_fastapi.services.robot_service_fastapi:RobotService",
    "services.robot_service_fastapi:RobotService",
    "robot_service_fastapi:RobotService",
    "..services:RobotService",  # relative fallback
]

for spec in _robot_import_attempts:
    if RobotService:
        break
    module_name, attr = spec.split(":")
    try:
        if module_name.startswith(".."):
            try:
                from ..services import RobotService as RS  # type: ignore
                RobotService = RS
                logging.getLogger(__name__).info(f"Loaded RobotService via relative import ({module_name})")
                break
            except Exception as e:  # pragma: no cover
                logging.getLogger(__name__).debug(f"Relative import failed ({module_name}): {e}")
                continue
        mod = importlib.import_module(module_name)
        RobotService = getattr(mod, attr, None)
        if RobotService:
            logging.getLogger(__name__).info(f"Loaded RobotService from {module_name}")
    except Exception as e:  # pragma: no cover
        logging.getLogger(__name__).debug(f"RobotService import attempt failed ({module_name}): {e}")

if RobotService is None:
    class RobotService:  # type: ignore
        """Lightweight mock robot service so GUI can operate without hardware.

        Provides the subset of attributes/methods used by the API layer.
        """
        def __init__(self, use_mock: bool = True, socketio=None):
            self.use_mock = use_mock
            self.socketio = socketio
            self.status = {
                "connected": False,
                "available_arms": ["left", "right"],
                "cameras": [],
                "error": None,
                "mode": None
            }

        def connect_aloha(self, overrides: list[str] | None = None):
            # Simulate a successful mock connection (not real hardware)
            self.status["connected"] = False  # keep False to signal mock_mode
            self.status["error"] = None
            return {
                "connected": False,
                "available_arms": self.status["available_arms"],
                "cameras": self.status["cameras"],
                "error": None,
            }

        def disconnect(self):
            self.status["connected"] = False
            self.status["mode"] = None

    class StreamService:  # type: ignore
        def __init__(self, socketio=None):
            self.socketio = socketio
        def start_camera_stream(self, *a, **k):
            return False
        def stop_camera_stream(self, *a, **k):
            return False
    # Ensure logger defined before use
    logging.getLogger(__name__).info("Using mock RobotService/StreamService (legacy services removed)")

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/robot", tags=["robot"])

# Pydantic models
class ApiResponse(BaseModel):
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None

class ConnectRequest(BaseModel):
    overrides: Optional[List[str]] = []
    leader_only: Optional[bool] = False
    show_cameras: Optional[bool] = True

# Global service instances
robot_service = None
stream_service = None

def initialize_services():
    """Initialize robot and stream services.

    Picks real hardware unless LEROBOT_GUI_FORCE_MOCK=1
    or RobotService import failed.
    """
    global robot_service, stream_service

    if RobotService and not robot_service:
        force_mock = os.getenv("LEROBOT_GUI_FORCE_MOCK") == "1"
        robot_service = RobotService(use_mock=force_mock)
        logger.info("Robot service initialized (mock=%s)", force_mock)

    if StreamService and not stream_service:
        socketio_instance = shared.get_socketio()
        if socketio_instance:
            stream_service = StreamService(socketio_instance)
            logger.info("Stream service initialized")
        else:
            logger.debug("Socket.IO instance not yet available for StreamService")

@router.on_event("startup")
async def startup_event():
    """Initialize services on router startup"""
    initialize_services()

@router.post("/connect", response_model=ApiResponse)
async def connect_robot(request: ConnectRequest):
    """
    Connect to ALOHA robot with enhanced configuration options
    
    Features:
    - Override configuration support
    - Leader-only mode option
    - Camera display control
    - Error handling and validation
    """
    try:
        logger.info(f"Connecting robot with overrides: {request.overrides}")
        
        if not robot_service:
            initialize_services()
            
        if not robot_service:
            # Should not happen because initialize_services creates mock, but guard anyway.
            raise HTTPException(
                status_code=503, 
                detail="Robot service not available. Check LeRobot installation."
            )
        
        # Connect to robot with basic configuration
        result = robot_service.connect_aloha(
            overrides=request.overrides or []
        )
        
        # Check if connection was successful
        is_connected = result.get("connected", False)
        error_message = result.get("error", None)
        
        if is_connected:
            logger.info("Robot connected successfully")
            message = "Robot connected successfully"
        else:
            if error_message:
                logger.warning(f"Robot hardware connection failed: {error_message}")
                message = "Robot hardware connection failed; mock mode"
            else:
                message = "Robot not connected (mock mode)"
        
        return ApiResponse(
            status="success",
            message=message,
            data={
                "connected": is_connected,
                "mock_mode": not is_connected,
                "leader_only": request.leader_only,
                "cameras_enabled": request.show_cameras,
                "overrides": request.overrides,
                "error": error_message,
                **result
            }
        )
        
    except Exception as e:
        logger.error(f"Robot connection failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to connect robot: {str(e)}"
        )

@router.post("/disconnect", response_model=ApiResponse)
async def disconnect_robot():
    """
    Disconnect from robot and cleanup resources
    
    Features:
    - Graceful disconnection
    - Resource cleanup
    - Status validation
    """
    try:
        logger.info("Disconnecting robot")
        
        if not robot_service:
            return ApiResponse(
                status="info",
                message="Robot was not connected",
                data={"connected": False}
            )
        
        # Disconnect robot
        robot_service.disconnect()
        
        logger.info("Robot disconnected successfully")
        return ApiResponse(
            status="success",
            message="Robot disconnected successfully",
            data={"connected": False}
        )
        
    except Exception as e:
        logger.error(f"Robot disconnection failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to disconnect robot: {str(e)}"
        )

@router.get("/status", response_model=ApiResponse)
async def get_robot_status():
    """
    Get current robot connection and health status
    
    Returns:
    - Connection status
    - Hardware health
    - Service availability
    - Mock mode indicator
    """
    try:
        if not robot_service:
            initialize_services()
        
        # Get robot status
        status_data = {
            "connected": robot_service.status["connected"] if robot_service else False,
            "mock_mode": not (robot_service and robot_service.status.get("connected")),
            "service_available": robot_service is not None,
            "stream_service": stream_service is not None
        }
        
        # Add hardware status if connected
        if robot_service and robot_service.status.get("connected", False):
            try:
                status_data.update({
                    "hardware_status": "healthy",
                    "leader_connected": True,
                    "follower_connected": True,
                    "cameras_active": False  # Update based on actual status
                })
            except Exception as e:
                logger.warning(f"Could not get hardware status: {e}")
                status_data["hardware_status"] = "unknown"
        
        return ApiResponse(
            status="success",
            message="Robot status retrieved",
            data=status_data
        )
        
    except Exception as e:
        logger.error(f"Failed to get robot status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get robot status: {str(e)}"
        )

@router.get("/info", response_model=ApiResponse)
async def get_robot_info():
    """
    Get detailed robot information and capabilities
    
    Returns:
    - Robot model and configuration
    - Available features
    - Supported operations
    """
    try:
        info_data = {
            "robot_type": "ALOHA",
            "mock_mode": True,
            "features": [
                "teleoperation",
                "recording", 
                "emergency_stop",
                "configuration_presets",
                "performance_monitoring"
            ],
            "supported_modes": [
                "bimanual",
                "leader_only"
            ],
            "preset_configurations": [
                "safe",
                "normal", 
                "performance"
            ]
        }
        
        return ApiResponse(
            status="success",
            message="Robot information retrieved",
            data=info_data
        )
        
    except Exception as e:
        logger.error(f"Failed to get robot info: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get robot info: {str(e)}"
        )

@router.get("/configs", response_model=ApiResponse)
async def get_robot_configs():
    """Return available robot configuration presets (placeholder)."""
    try:
        data = {
            "presets": [
                {"name": "safe", "description": "Lowest motion limits, high safety margins"},
                {"name": "normal", "description": "Balanced defaults for development"},
                {"name": "performance", "description": "Higher speed & range (use caution)"}
            ],
            "supports_overrides": True,
            "available_arms": robot_service.status["available_arms"] if robot_service else []
        }
        return ApiResponse(status="success", message="Robot configs retrieved", data=data)
    except Exception as e:
        logger.error(f"Failed to get robot configs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get robot configs: {e}")
