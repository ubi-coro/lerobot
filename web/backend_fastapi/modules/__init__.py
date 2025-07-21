"""
LeRobot FastAPI Backend Modules
===============================

This package contains modular FastAPI routers organized by functionality,
inspired by LeLab's clean architecture but enhanced with LeRobot's advanced features.

Modules:
- teleoperation.py - Advanced teleoperation with preset configurations
- robot.py - Robot connection and hardware management
- safety.py - Emergency stop and safety systems
- monitoring.py - Performance monitoring and health checks
- recording.py - Dataset recording (inspired by LeLab)
- configuration.py - Configuration management
"""

__all__ = [
    "teleoperation",
    "robot", 
    "safety",
    "monitoring",
    "recording",
    "configuration"
]
