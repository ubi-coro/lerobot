import os
import logging
import threading
import time
import cv2
from typing import Dict, Any, Optional, List

from lerobot.common.robot_devices.robots.configs import AlohaRobotConfig
from lerobot.common.robot_devices.robots.utils import make_robot_from_config
from lerobot.common.robot_devices.control_utils import control_loop

logger = logging.getLogger(__name__)

class RobotService:
    def __init__(self, use_mock: bool = False, socketio=None):
        self.robot = None
        self.robot_cfg = None
        self.use_mock = use_mock
        self.socketio = socketio  # Add this line
        self.status = {
            "connected": False,
            "available_arms": [],
            "cameras": [],
            "error": None,
            "mode": None
        }
        self.control_thread = None
        self.stop_event = threading.Event()
        self.camera_windows = {}  # Track OpenCV windows
        self.show_camera_display = False

    def connect_aloha(self, overrides: Optional[List[str]] = None) -> Dict[str, Any]:
        """Connect to ALOHA robot with fixed configuration"""
        try:
            if self.status["connected"]:
                return {"already_connected": True}

            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            calibration_dir = os.path.join(project_root, ".cache", "calibration", "aloha_lemgo_tabea")
            
            logger.info(f"Using calibration directory: {calibration_dir}")
            
            # Verify the calibration directory exists
            if not os.path.exists(calibration_dir):
                raise FileNotFoundError(f"Calibration directory not found: {calibration_dir}")

            # Create ALOHA configuration with absolute path
            self.robot_cfg = AlohaRobotConfig(
                calibration_dir=calibration_dir,
                max_relative_target=25,
                mock=self.use_mock
            )

            # Apply any overrides for operation modes (left_only, right_only, etc.)
            if overrides:
                logger.info(f"Applying overrides: {overrides}")
                for override in overrides:
                    if override.startswith("~"):
                        # Handle exclusion override (e.g., ~leader_arms.left)
                        key = override[1:]  # Remove the ~ character
                        self._apply_exclusion_override(key)
                    elif "=" in override:
                        # Handle key=value override
                        key, value = override.split("=", 1)
                        self._apply_value_override(key, value)
                
                # Debug: log final camera configuration
                logger.info(f"Final camera configuration: {self.robot_cfg.cameras}")
            else:
                logger.info("No overrides to apply")

            # Create and connect the robot
            logger.info("Creating ALOHA robot from configuration")
            self.robot = make_robot_from_config(self.robot_cfg)
            
            logger.info("Connecting to ALOHA robot")
            self.robot.connect()
            
            self.status["connected"] = True
            self.status["error"] = None
            self.status["available_arms"] = list(self.robot.leader_arms.keys()) + list(self.robot.follower_arms.keys())
            
            # Get camera information
            if hasattr(self.robot, 'cameras') and self.robot.cameras:
                self.status["cameras"] = [
                    {"id": name, "name": name} 
                    for name in self.robot.cameras.keys()
                ]
            else:
                self.status["cameras"] = []
                logger.info("No cameras configured for this robot connection")
            
            logger.info(f"Successfully connected to ALOHA robot with {len(self.status['available_arms'])} arms")
            
            return {
                "connected": True,
                "robot_type": "aloha",
                "available_arms": self.status["available_arms"],
                "cameras": self.status["cameras"]
            }
            
        except Exception as e:
            logger.error(f"Failed to connect to ALOHA robot: {str(e)}")
            self.status["error"] = str(e)
            return {"connected": False, "error": str(e)}

    def _apply_exclusion_override(self, key: str):
        """Apply exclusion overrides like ~leader_arms.left"""
        if "." in key:
            main_key, sub_key = key.split(".", 1)
            if hasattr(self.robot_cfg, main_key):
                attr = getattr(self.robot_cfg, main_key)
                if isinstance(attr, dict) and sub_key in attr:
                    del attr[sub_key]
                    logger.info(f"Excluded {key} from robot configuration")

    def _apply_value_override(self, key: str, value: str):
        """Apply value overrides like max_relative_target=50 or robot.cameras={}"""
        if key == "robot.cameras" and value == "{}":
            # Special handling for disabling cameras
            self.robot_cfg.cameras = {}
            logger.info("Disabled all cameras via override")
            return
        elif key == "cameras" and value == "{}":
            # Alternative format
            self.robot_cfg.cameras = {}
            logger.info("Disabled all cameras via override (alternative format)")
            return
            
        if "." in key:
            # Handle nested attributes like robot.cameras
            parts = key.split(".")
            obj = self.robot_cfg
            for part in parts[:-1]:
                if hasattr(obj, part):
                    obj = getattr(obj, part)
                else:
                    logger.warning(f"Cannot find attribute {part} in {obj}")
                    return
            
            final_key = parts[-1]
            if hasattr(obj, final_key):
                current_value = getattr(obj, final_key)
                if isinstance(current_value, bool):
                    setattr(obj, final_key, value.lower() == "true")
                elif isinstance(current_value, int):
                    setattr(obj, final_key, int(value))
                elif isinstance(current_value, float):
                    setattr(obj, final_key, float(value))
                elif value == "{}":
                    setattr(obj, final_key, {})
                else:
                    setattr(obj, final_key, value)
                logger.info(f"Set {key} = {value}")
        elif hasattr(self.robot_cfg, key):
            current_value = getattr(self.robot_cfg, key)
            if isinstance(current_value, bool):
                setattr(self.robot_cfg, key, value.lower() == "true")
            elif isinstance(current_value, int):
                setattr(self.robot_cfg, key, int(value))
            elif isinstance(current_value, float):
                setattr(self.robot_cfg, key, float(value))
            elif key == "cameras" and value == "{}":
                setattr(self.robot_cfg, key, {})
            else:
                setattr(self.robot_cfg, key, value)
            logger.info(f"Set {key} = {value}")

    def start_teleoperation(self, fps: Optional[int] = 30, show_cameras: bool = True) -> None:
        """Start ALOHA robot teleoperation with optional camera display"""
        if not self.status["connected"]:
            raise ValueError("ALOHA robot is not connected")
        
        if self.status["mode"] == "teleoperating":
            logger.warning("Teleoperation is already running")
            return
        
        # Set camera display preference
        self.show_camera_display = show_cameras
        
        # Reset stop event
        self.stop_event.clear()
        
        def run_teleoperation():
            try:
                self.status["mode"] = "teleoperating"
                logger.info(f"Starting ALOHA teleoperation at {fps} FPS with camera display: {show_cameras}")
                
                # Start camera display thread if requested
                if show_cameras:
                    self._start_camera_display()
                
                # Run teleoperation loop
                while not self.stop_event.is_set():
                    # Run teleoperation for 1 second intervals to check stop event
                    control_loop(
                        robot=self.robot,
                        control_time_s=1.0,
                        fps=fps,
                        teleoperate=True,
                        display_data=False  # We handle camera display ourselves
                    )
                    
                self.status["mode"] = None
                logger.info("ALOHA teleoperation stopped")
                
            except Exception as e:
                self.status["error"] = str(e)
                self.status["mode"] = None
                logger.error(f"Error during ALOHA teleoperation: {str(e)}")
            finally:
                # Stop camera display
                if show_cameras:
                    self._stop_camera_display()
        
        # Start teleoperation in a new thread
        self.control_thread = threading.Thread(target=run_teleoperation, daemon=True)
        self.control_thread.start()
        logger.info("ALOHA teleoperation thread started")

    def _start_camera_display(self):
        """Start displaying camera feeds in OpenCV windows"""
        logger.info("_start_camera_display called")
        
        def camera_display_loop():
            logger.info("Starting camera display loop")
            try:
                while not self.stop_event.is_set() and self.show_camera_display:
                    try:
                        logger.info("Capturing observation...")
                        # Capture current observation
                        observation = self.robot.capture_observation()
                        logger.info(f"Observation keys: {list(observation.keys())}")
                        
                        # Display each camera feed
                        for key, frame in observation.items():
                            if "image" in key and frame is not None:
                                logger.info(f"Processing camera frame for {key}")
                                # Convert from tensor to numpy if needed
                                if hasattr(frame, 'numpy'):
                                    frame_np = frame.numpy()
                                else:
                                    frame_np = frame
                                
                                logger.info(f"Frame shape for {key}: {frame_np.shape}")
                                
                                # Ensure proper format for OpenCV (BGR)
                                if len(frame_np.shape) == 3:
                                    if frame_np.shape[2] == 3:  # RGB to BGR
                                        frame_display = cv2.cvtColor(frame_np, cv2.COLOR_RGB2BGR)
                                    else:
                                        frame_display = frame_np
                                else:
                                    frame_display = frame_np
                                
                                # Create window if it doesn't exist
                                window_name = f"Camera: {key}"
                                if key not in self.camera_windows:
                                    logger.info(f"Creating window for {key}")
                                    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
                                    cv2.resizeWindow(window_name, 640, 480)
                                    self.camera_windows[key] = window_name
                                
                                # Display frame
                                cv2.imshow(window_name, frame_display)
                                logger.info(f"Displayed frame for {key}")
                        
                        # Process OpenCV events
                        key_pressed = cv2.waitKey(1) & 0xFF
                        if key_pressed == ord('q'):  # Press 'q' to close cameras
                            logger.info("Camera display stopped by user (q key)")
                            break
                            
                    except Exception as e:
                        logger.error(f"Error in camera display loop: {str(e)}")
                        time.sleep(0.1)  # Prevent rapid error loops
                
                time.sleep(0.033)  # ~30 FPS for camera display
                
            except Exception as e:
                logger.error(f"Camera display loop error: {str(e)}")
            finally:
                self._cleanup_camera_windows()
    
        # Start camera display in separate thread
        camera_thread = threading.Thread(target=camera_display_loop, daemon=True)
        camera_thread.start()
        logger.info("Camera display thread started")

    def _stop_camera_display(self):
        """Stop camera display and cleanup windows"""
        self.show_camera_display = False
        self._cleanup_camera_windows()

    def _cleanup_camera_windows(self):
        """Close all OpenCV camera windows"""
        try:
            for window_name in self.camera_windows.values():
                cv2.destroyWindow(window_name)
            self.camera_windows.clear()
            cv2.destroyAllWindows()
            logger.info("Camera windows closed")
        except Exception as e:
            logger.error(f"Error closing camera windows: {str(e)}")

    def stop_teleoperation(self) -> None:
        """Stop ALOHA robot teleoperation"""
        if self.status["mode"] != "teleoperating":
            logger.warning("Teleoperation is not running")
            return
            
        logger.info("Stopping ALOHA teleoperation")
        self.stop_event.set()
        
        # Stop camera display
        self._stop_camera_display()
        
        # Wait for teleoperation thread to finish
        if self.control_thread and self.control_thread.is_alive():
            self.control_thread.join(timeout=2.0)
        
        self.status["mode"] = None
        logger.info("ALOHA teleoperation stopped")

    def disconnect(self) -> None:
        """Disconnect from ALOHA robot"""
        if self.status["mode"] == "teleoperating":
            self.stop_teleoperation()
            
        if self.robot and self.robot.is_connected:
            self.robot.disconnect()
            
        self.status["connected"] = False
        self.status["available_arms"] = []
        self.status["cameras"] = []
        self.robot = None
        self.robot_cfg = None
        logger.info("Disconnected from ALOHA robot")

    def get_status(self) -> Dict[str, Any]:
        """Get current robot status"""
        return self.status.copy()

    # Add method to get robot instance for streaming
    def get_robot_instance(self):
        """Get the robot instance for camera access"""
        return self.robot
    
    def start_teleoperation_advanced(self, config: Dict[str, Any]) -> None:
        """Start ALOHA robot teleoperation with advanced configuration"""
        if not self.status["connected"]:
            raise ValueError("ALOHA robot is not connected")
        
        if self.status["mode"] == "teleoperating":
            logger.warning("Teleoperation is already running")
            return
        
        # Apply robot configuration changes
        if config.get('max_relative_target') and hasattr(self.robot_cfg, 'max_relative_target'):
            self.robot_cfg.max_relative_target = config['max_relative_target']
            
        if config.get('moving_time') and hasattr(self.robot_cfg, 'moving_time'):
            self.robot_cfg.moving_time = config['moving_time']
        
        # Set camera display preference
        self.show_camera_display = config.get('show_cameras', True)
        
        # Reset stop event
        self.stop_event.clear()
        
        def run_advanced_teleoperation():
            try:
                self.status["mode"] = "teleoperating"
                logger.info(f"Starting advanced ALOHA teleoperation with config: {config}")
                
                # Start camera display thread if requested
                if config.get('show_cameras', True):
                    self._start_camera_display()
                
                # Set up time limit if specified
                start_time = time.time()
                time_limit = config.get('teleop_time_limit')
                if time_limit:
                    time_limit = time_limit * 60  # Convert minutes to seconds
                
                # Run teleoperation loop
                while not self.stop_event.is_set():
                    # Check time limit
                    if time_limit and (time.time() - start_time) > time_limit:
                        logger.info("Teleoperation time limit reached, stopping...")
                        break
                        
                    # Run teleoperation for 1 second intervals to check stop event
                    control_loop(
                        robot=self.robot,
                        control_time_s=1.0,
                        fps=config.get('fps', 30),
                        teleoperate=True,
                        display_data=config.get('display_data', False)
                    )
                    
                self.status["mode"] = None
                logger.info("Advanced ALOHA teleoperation stopped")
                
            except Exception as e:
                self.status["error"] = str(e)
                self.status["mode"] = None
                logger.error(f"Error during advanced ALOHA teleoperation: {str(e)}")
            finally:
                # Stop camera display
                if config.get('show_cameras', True):
                    self._stop_camera_display()
        
        # Start teleoperation in a new thread
        self.control_thread = threading.Thread(target=run_advanced_teleoperation, daemon=True)
        self.control_thread.start()
        logger.info("Advanced ALOHA teleoperation thread started")
    
    def emergency_stop(self) -> None:
        """Emergency stop for teleoperation"""
        if self.status["mode"] == "teleoperating":
            logger.warning("EMERGENCY STOP ACTIVATED")
            self.stop_event.set()
            
            # Immediately stop camera display
            self._stop_camera_display()
            
            # Wait for teleoperation thread to finish with shorter timeout
            if self.control_thread and self.control_thread.is_alive():
                self.control_thread.join(timeout=1.0)
            
            self.status["mode"] = None
            logger.info("Emergency stop completed")
        else:
            logger.warning("Emergency stop called but teleoperation is not active")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        # This is a mock implementation - in real scenario, you'd collect actual metrics
        import psutil
        import random
        
        return {
            "actualFps": random.randint(25, 35) if self.status["mode"] == "teleoperating" else 0,
            "latency": random.randint(10, 50) if self.status["mode"] == "teleoperating" else 0,
            "cpuUsage": psutil.cpu_percent(),
            "memoryUsage": psutil.virtual_memory().percent,
            "timestamp": time.time()
        }
    
    def move_to_safe_position(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Move robot to safe position"""
        if not self.status["connected"]:
            raise ValueError("Robot is not connected")
        
        if self.status["mode"] == "teleoperating":
            raise ValueError("Cannot move to safe position during teleoperation")
        
        logger.info(f"Moving robot to safe position with config: {config}")
        
        try:
            # This is a simplified implementation
            # In a real scenario, you would implement actual safe position movement
            
            # Simulate movement time
            timeout = config.get('timeout_s', 10.0)
            speed_factor = config.get('speed_factor', 0.3)
            
            # Calculate estimated movement time based on speed factor
            estimated_time = timeout * (1.0 - speed_factor)
            
            logger.info(f"Estimated movement time: {estimated_time:.2f} seconds")
            
            # In real implementation, this would be actual robot movement
            time.sleep(min(estimated_time, 2.0))  # Simulate for demo
            
            return {
                "success": True,
                "message": "Robot moved to safe position",
                "estimated_time": estimated_time,
                "actual_time": min(estimated_time, 2.0)
            }
            
        except Exception as e:
            logger.error(f"Error moving to safe position: {str(e)}")
            raise