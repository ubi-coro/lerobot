"""
Service Bridge - Mock Implementation
===================================

Simple mock service bridge for backward compatibility when the full
Flask service bridge is not available.

This allows the modular FastAPI backend to run independently without
requiring the full Flask backend services.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ServiceBridge:
    """Mock service bridge for development and testing"""
    
    def __init__(self):
        self.mock_mode = True
        logger.info("🔧 Mock service bridge initialized")
    
    def get_robot_status(self) -> Dict[str, Any]:
        """Get mock robot status"""
        return {
            "status": "disconnected",
            "mode": "mock",
            "is_connected": False,
            "message": "Mock service bridge - robot not connected",
            "cameras_enabled": False,
            "mock_mode": True
        }
    
    def connect_robot(self, **kwargs) -> Dict[str, Any]:
        """Mock robot connection"""
        return {
            "status": "success",
            "message": "Mock robot connection established",
            "mock_mode": True
        }
    
    def disconnect_robot(self) -> Dict[str, Any]:
        """Mock robot disconnection"""
        return {
            "status": "success", 
            "message": "Mock robot disconnected",
            "mock_mode": True
        }
    
    def emergency_stop(self) -> Dict[str, Any]:
        """Mock emergency stop"""
        logger.critical("🛑 MOCK EMERGENCY STOP")
        return {
            "status": "success",
            "message": "Mock emergency stop executed",
            "mock_mode": True
        }
    
    def start_teleoperation(self, **kwargs) -> Dict[str, Any]:
        """Mock teleoperation start"""
        return {
            "status": "success",
            "message": "Mock teleoperation started",
            "mock_mode": True
        }
    
    def stop_teleoperation(self) -> Dict[str, Any]:
        """Mock teleoperation stop"""
        return {
            "status": "success",
            "message": "Mock teleoperation stopped", 
            "mock_mode": True
        }
