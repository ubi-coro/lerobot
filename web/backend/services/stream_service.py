import threading
import time
import logging
import base64
import cv2
import numpy as np
from io import BytesIO
from PIL import Image
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class StreamService:
    def __init__(self, socketio):
        self.socketio = socketio
        self.robot_service = None  # Will be set after initialization
        self.camera_threads = {}
        self.stop_events = {}
        
    def set_robot_service(self, robot_service):
        """Set the robot service reference"""
        self.robot_service = robot_service
        
    def start_camera_stream(self, camera_id: str, fps: int = 10) -> None:
        """Start streaming a camera feed"""
        if camera_id in self.camera_threads and self.camera_threads[camera_id].is_alive():
            logger.info(f"Camera stream for {camera_id} is already running")
            return
            
        if not self.robot_service or not self.robot_service.robot:
            logger.error("Robot is not connected")
            return
            
        # Find the camera
        camera = None
        if hasattr(self.robot_service.robot, 'cameras'):
            for cam in self.robot_service.robot.cameras:
                if cam.camera_id == camera_id:
                    camera = cam
                    break
                    
        if not camera:
            logger.error(f"Camera {camera_id} not found")
            return
            
        # Create stop event
        stop_event = threading.Event()
        self.stop_events[camera_id] = stop_event
        
        # Create streaming thread
        def stream_camera():
            logger.info(f"Starting camera stream for {camera_id}")
            
            # Calculate delay based on FPS
            delay = 1.0 / fps if fps > 0 else 0.1
            
            while not stop_event.is_set():
                try:
                    # Capture frame
                    frame = camera.get_image()
                    
                    if frame is not None:
                        # Convert to JPEG
                        success, buffer = cv2.imencode('.jpg', frame)
                        if success:
                            # Convert to base64 for sending over socket
                            frame_bytes = base64.b64encode(buffer).decode('utf-8')
                            
                            # Emit frame to client
                            self.socketio.emit('camera_frame', {
                                'camera_id': camera_id,
                                'frame': frame_bytes
                            })
                    
                    # Sleep to maintain FPS
                    time.sleep(delay)
                except Exception as e:
                    logger.error(f"Error streaming camera {camera_id}: {str(e)}")
                    time.sleep(1)  # Wait before trying again
        
        # Start thread
        thread = threading.Thread(target=stream_camera)
        thread.daemon = True
        thread.start()
        self.camera_threads[camera_id] = thread
        
    def stop_camera_stream(self, camera_id: str) -> None:
        """Stop streaming a camera feed"""
        if camera_id in self.stop_events:
            logger.info(f"Stopping camera stream for {camera_id}")
            self.stop_events[camera_id].set()
            
            if camera_id in self.camera_threads:
                self.camera_threads[camera_id].join(timeout=2)
                del self.camera_threads[camera_id]
                
            del self.stop_events[camera_id]
            
    def stop_all_streams(self) -> None:
        """Stop all camera streams"""
        logger.info("Stopping all camera streams")
        for camera_id in list(self.stop_events.keys()):
            self.stop_camera_stream(camera_id)