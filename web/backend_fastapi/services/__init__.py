"""
Service Import Bridge
====================

This module imports the existing Flask services to be used by FastAPI.
This allows us to reuse the existing robot and stream services during migration.
"""

import sys
import os

# Add the Flask backend services path to import existing services
flask_services_path = os.path.join(os.path.dirname(__file__), '../../backend/services')
sys.path.insert(0, flask_services_path)

# Import existing services directly
try:
    from robot_service import RobotService
    from stream_service import StreamService
    
    print("✅ Successfully imported existing services")
    
except ImportError as e:
    print(f"⚠️ Could not import services: {e}")
    
    # Create mock services for development
    class MockRobotService:
        def __init__(self, use_mock=True):
            self.use_mock = use_mock
            self.status = {"mode": None, "is_connected": False}
        
        def connect_aloha(self, overrides=None, enable_cameras=True):
            return {"status": "connected", "mock": True}
        
        def disconnect(self):
            self.status = {"mode": None, "is_connected": False}
        
        def start_teleoperation(self, fps=30, show_cameras=True):
            self.status["mode"] = "teleoperating"
        
        def stop_teleoperation(self):
            self.status["mode"] = None
        
        def emergency_stop(self):
            self.status["mode"] = None
        
        def get_status(self):
            return self.status
        
        def get_performance_metrics(self):
            return {"fps": 30, "latency": 15}
    
    class MockStreamService:
        def __init__(self):
            pass
    
    RobotService = MockRobotService
    StreamService = MockStreamService
    
    print("✅ Using mock services for development")

# Export for use by FastAPI
__all__ = ['RobotService', 'StreamService']
