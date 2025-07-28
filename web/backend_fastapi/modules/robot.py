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

# Import shared state
import shared

# Import existing services via bridge
try:
    from ..services import RobotService, StreamService
except ImportError:
    try:
        sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
        from services import RobotService, StreamService
    except ImportError as e:
        logging.warning(f"Could not import services: {e}")
        RobotService = None
        StreamService = None

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
    """Initialize robot and stream services"""
    global robot_service, stream_service
    
    if RobotService and not robot_service:
        robot_service = RobotService(use_mock=True)  # Start in mock mode
        logger.info("Robot service initialized")
    
    if StreamService and not stream_service:
        socketio_instance = shared.get_socketio()
        if socketio_instance:
            stream_service = StreamService(socketio_instance)
            logger.info("Stream service initialized")
        else:
            logger.warning("Socket.IO instance not available for StreamService")

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
            raise HTTPException(
                status_code=503, 
                detail="Robot service not available. Check LeRobot installation."
            )
        
        # Connect to robot with enhanced options
        result = robot_service.connect_aloha(
            overrides=request.overrides or [],
            leader_only=request.leader_only,
            show_cameras=request.show_cameras
        )
        
        logger.info("Robot connected successfully")
        return ApiResponse(
            status="success",
            message="Robot connected successfully",
            data={
                "connected": True,
                "leader_only": request.leader_only,
                "cameras_enabled": request.show_cameras,
                "overrides": request.overrides,
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
            "mock_mode": True,  # Currently in mock mode
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
