import threading
import logging
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import numpy as np
import time
import cv2
from threading import Thread

# Import LeRobot modules
from lerobot.common.robot_devices.robots.utils import make_robot_from_config as make_robot
from lerobot.configs import parser
from lerobot.scripts.control_robot import calibrate, teleoperate, record

logger = logging.getLogger(__name__)

class MockRobot:
    """A mock robot implementation for testing without hardware"""
    def __init__(self, robot_type="aloha"):
        self.robot_type = robot_type
        self.connected = False
        self.available_arms = ["left_arm", "right_arm"]
        self.cameras = [MockCamera("front_camera"), MockCamera("wrist_camera")]
    
    def connect(self):
        self.connected = True
        time.sleep(1)  # Simulate connection time
    
    def disconnect(self):
        self.connected = False
    
    def is_connected(self):
        return self.connected
    
    def send_action(self, action):
        # Just pretend to do something with the action
        pass

class MockCamera:
    """A mock camera that generates random images"""
    def __init__(self, camera_id):
        self.camera_id = camera_id
        self.width = 320
        self.height = 240
    
    def get_image(self):
        # Generate a random colored test pattern
        img = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Add timestamp
        timestamp = time.strftime("%H:%M:%S")
        
        # Different pattern for different cameras
        if "front" in self.camera_id:
            # Draw some colored rectangles
            img[50:100, 50:100] = [255, 0, 0]  # Red rectangle
            img[100:150, 150:200] = [0, 255, 0]  # Green rectangle
            img[150:200, 100:150] = [0, 0, 255]  # Blue rectangle
        else:
            # Draw a pattern of circles
            center = (self.width // 2, self.height // 2)
            for r in range(0, 100, 20):
                color = [(r * 2) % 255, (r * 3) % 255, (r * 5) % 255]
                cv2.circle(img, center, r, color, 5)
        
        # Add camera ID and timestamp text
        cv2.putText(img, f"{self.camera_id} - {timestamp}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        return img

class RobotService:
    def __init__(self, use_mock=False):
        self.robot = None
        self.robot_cfg = None
        self.status = {
            "connected": False,
            "mode": None,
            "error": None,
            "cameras": [],
            "available_arms": []
        }
        self.control_thread = None
        self.stop_event = threading.Event()
        self.use_mock = use_mock

    def get_status(self) -> Dict[str, Any]:
        """Get current robot status"""
        return self.status

    def connect(self, robot_config: str, robot_overrides: Optional[List[str]] = None) -> Dict[str, Any]:
        """Connect to the robot with the specified configuration"""
        if self.status["connected"]:
            return {"already_connected": True}
        
        try:
            if self.use_mock:
                # Create a mock robot instead of real hardware
                self.robot = MockRobot(robot_type=robot_config.split('/')[-1].replace('.yaml', ''))
                self.robot.connect()
                
                self.status["connected"] = True
                self.status["error"] = None
                self.status["available_arms"] = self.robot.available_arms
                
                # Get camera information
                if hasattr(self.robot, 'cameras') and self.robot.cameras:
                    self.status["cameras"] = [
                        {"id": cam.camera_id, "name": cam.camera_id} 
                        for cam in self.robot.cameras
                    ]
                
                logger.info(f"Connected to mock robot {self.robot.robot_type}")
                
                return {
                    "connected": True,
                    "robot_type": self.robot.robot_type,
                    "available_arms": self.status["available_arms"],
                    "cameras": self.status["cameras"]
                }
            else:
                # Initialize robot configuration
                self.robot_cfg = parser.parse_config(robot_config, overrides=robot_overrides)
                self.robot = make_robot(self.robot_cfg)
                
                # Connect to robot
                self.robot.connect()
                self.status["connected"] = True
                self.status["error"] = None
                self.status["available_arms"] = self.robot.available_arms if hasattr(self.robot, 'available_arms') else []
                
                # Get camera information
                if hasattr(self.robot, 'cameras') and self.robot.cameras:
                    self.status["cameras"] = [
                        {"id": cam.camera_id, "name": cam.camera_id} 
                        for cam in self.robot.cameras
                    ]
                
                logger.info(f"Connected to robot {self.robot.robot_type}")
                
                return {
                    "connected": True,
                    "robot_type": self.robot.robot_type,
                    "available_arms": self.status["available_arms"],
                    "cameras": self.status["cameras"]
                }
        except Exception as e:
            self.status["error"] = str(e)
            logger.error(f"Error connecting to robot: {str(e)}")
            raise

    def disconnect(self) -> None:
        """Disconnect from the robot"""
        if not self.status["connected"]:
            return
        
        try:
            # Stop any ongoing operation
            self.stop_event.set()
            if self.control_thread and self.control_thread.is_alive():
                self.control_thread.join(timeout=5)
            
            # Disconnect the robot
            self.robot.disconnect()
            self.status["connected"] = False
            self.status["mode"] = None
            self.stop_event.clear()
            logger.info("Disconnected from robot")
        except Exception as e:
            self.status["error"] = str(e)
            logger.error(f"Error disconnecting robot: {str(e)}")
            raise

    def teleoperate(self, fps: Optional[int] = None, display_cameras: bool = True) -> None:
        """Start robot teleoperation"""
        if not self.status["connected"]:
            raise ValueError("Robot is not connected")
        
        # Reset stop event
        self.stop_event.clear()
        
        def run_teleoperation():
            try:
                self.status["mode"] = "teleoperating"
                logger.info(f"Starting teleoperation at {fps if fps else 'max'} FPS")
                
                # Set up a polling loop to check stop_event
                while not self.stop_event.is_set():
                    # Run teleoperation for short intervals to check stop event
                    teleop_interval = 1.0  # 1 second at a time
                    teleoperate(
                        self.robot, 
                        fps=fps, 
                        teleop_time_s=teleop_interval,
                        display_cameras=display_cameras
                    )
                    
                self.status["mode"] = None
                logger.info("Teleoperation stopped")
            except Exception as e:
                self.status["error"] = str(e)
                self.status["mode"] = None
                logger.error(f"Error during teleoperation: {str(e)}")
        
        # Start teleoperation in a new thread
        self.control_thread = threading.Thread(target=run_teleoperation)
        self.control_thread.daemon = True  # Make thread a daemon so it exits when main thread exits
        self.control_thread.start()
        logger.info("Teleoperation thread started")

    def stop_teleoperation(self) -> None:
        """Stop robot teleoperation"""
        if self.status["mode"] != "teleoperating":
            return
        
        logger.info("Stopping teleoperation...")
        self.stop_event.set()
        if self.control_thread and self.control_thread.is_alive():
            self.control_thread.join(timeout=5)
        
        self.status["mode"] = None
        logger.info("Teleoperation stopped")

    def send_action(self, action: List[float]) -> None:
        """Send a single action to the robot"""
        if not self.status["connected"]:
            raise ValueError("Robot is not connected")
        
        try:
            self.robot.send_action(action)
        except Exception as e:
            self.status["error"] = str(e)
            logger.error(f"Error sending action: {str(e)}")
            raise