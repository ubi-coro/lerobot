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
        self.active_streams = {}
        
    def set_robot_service(self, robot_service):
        """Set the robot service reference"""
        self.robot_service = robot_service
        
    def start_camera_stream(self, camera_id: str, fps: int = 10) -> None:
        """Start streaming a camera feed"""
        if camera_id in self.active_streams:
            return  # Already streaming
            
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
            
        # Start stream
        stream_thread = threading.Thread(target=self._stream_camera, args=(camera, camera_id, fps))
        stream_thread.daemon = True
        stream_thread.start()
        
        self.active_streams[camera_id] = {
            'thread': stream_thread,
            'stop': False
        }
        
        logger.info(f"Started streaming camera {camera_id}")
        
    def _stream_camera(self, camera, camera_id, fps):
        logger.info(f"Starting camera stream for {camera_id}")
        
        # Calculate delay based on FPS
        delay = 1.0 / fps if fps > 0 else 0.1
        
        while not self.active_streams[camera_id]['stop']:
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
        
    def stop_camera_stream(self, camera_id: str) -> None:
        """Stop streaming a camera feed"""
        if camera_id in self.active_streams:
            logger.info(f"Stopping camera stream for {camera_id}")
            self.active_streams[camera_id]['stop'] = True
            self.active_streams[camera_id]['thread'].join(timeout=2)
            del self.active_streams[camera_id]
            
    def stop_all_streams(self) -> None:
        """Stop all camera streams"""
        logger.info("Stopping all camera streams")
        for camera_id in list(self.active_streams.keys()):
            self.stop_camera_stream(camera_id)