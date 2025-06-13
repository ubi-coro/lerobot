import logging
import threading
import time
import base64
import cv2
import numpy as np
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class StreamService:
    def __init__(self, socketio):
        self.socketio = socketio
        self.active_streams = {}
        self.stream_threads = {}
        self.stop_events = {}
        logger.info("StreamService initialized")

    def start_camera_stream(self, camera_id: str, fps: int = 10, robot=None):
        """Start camera streaming with real camera data"""
        if camera_id in self.active_streams:
            logger.warning(f"Camera stream {camera_id} is already active")
            return

        logger.info(f"Starting camera stream for {camera_id} at {fps} FPS")
        
        # Create stop event for this camera
        stop_event = threading.Event()
        self.stop_events[camera_id] = stop_event
        
        # Start streaming thread
        stream_thread = threading.Thread(
            target=self._stream_camera,
            args=(camera_id, fps, stop_event, robot),
            daemon=True
        )
        
        self.active_streams[camera_id] = {'fps': fps, 'active': True}
        self.stream_threads[camera_id] = stream_thread
        stream_thread.start()

    def _stream_camera(self, camera_id: str, fps: int, stop_event: threading.Event, robot=None):
        """Stream camera frames via Socket.IO"""
        logger.info(f"Starting camera stream thread for {camera_id}")
        
        try:
            frame_interval = 1.0 / fps
            frame_count = 0
            
            while not stop_event.is_set():
                start_time = time.time()
                
                # Get camera frame
                frame = self._get_camera_frame(camera_id, robot)
                
                if frame is not None:
                    # Convert frame to base64 for transmission
                    frame_data = self._frame_to_base64(frame)
                    
                    # Emit frame via Socket.IO
                    self.socketio.emit('camera_frame', {
                        'camera_id': camera_id,
                        'frame': frame_data,
                        'timestamp': time.time()
                    })
                    
                    frame_count += 1
                    if frame_count % 30 == 0:  # Log every 30 frames
                        logger.info(f"Sent {frame_count} frames for {camera_id}")
            
                # Maintain FPS
                elapsed = time.time() - start_time
                sleep_time = max(0, frame_interval - elapsed)
                time.sleep(sleep_time)
                
        except Exception as e:
            logger.error(f"Error in camera stream {camera_id}: {str(e)}")
        finally:
            # Cleanup
            if camera_id in self.active_streams:
                del self.active_streams[camera_id]
            logger.info(f"Camera stream {camera_id} stopped")

    def _get_camera_frame(self, camera_id: str, robot=None):
        """Get frame from ALOHA robot camera"""
        logger.info(f"=== GETTING FRAME FOR {camera_id} ===")
        logger.info(f"Robot provided: {robot is not None}")
        
        try:
            if robot and hasattr(robot, 'cameras'):
                logger.info(f"Robot cameras available: {list(robot.cameras.keys())}")
                if camera_id in robot.cameras:
                    logger.info(f"Camera {camera_id} found in robot")
                    camera = robot.cameras[camera_id]
                    frame = camera.read()
                    logger.info(f"Frame captured: {frame.shape if frame is not None else 'None'}")
                    return frame
                else:
                    logger.warning(f"Camera {camera_id} not found in robot cameras")
            else:
                logger.warning(f"No robot or no cameras attribute")
                
            # Fallback: generate test pattern
            logger.info(f"Generating test frame for {camera_id}")
            return self._generate_test_frame(camera_id)
        
        except Exception as e:
            logger.error(f"Error reading camera {camera_id}: {str(e)}")
            return self._generate_test_frame(camera_id)

    def _generate_test_frame(self, camera_id: str):
        """Generate a test frame with camera info"""
        # Create a 640x480 test image
        height, width = 480, 640
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Add camera ID text
        cv2.putText(frame, f"Camera: {camera_id}", (50, 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        # Add timestamp
        timestamp = time.strftime("%H:%M:%S")
        cv2.putText(frame, f"Time: {timestamp}", (50, 100), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        # Add some color patterns
        cv2.rectangle(frame, (50, 150), (150, 250), (0, 255, 0), -1)  # Green
        cv2.rectangle(frame, (200, 150), (300, 250), (255, 0, 0), -1)  # Blue
        cv2.rectangle(frame, (350, 150), (450, 250), (0, 0, 255), -1)  # Red
        
        return frame

    def _frame_to_base64(self, frame):
        """Convert OpenCV frame to base64 string"""
        try:
            # Encode frame as JPEG
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            
            # Convert to base64
            frame_base64 = base64.b64encode(buffer).decode('utf-8')
            return f"data:image/jpeg;base64,{frame_base64}"
            
        except Exception as e:
            logger.error(f"Error encoding frame: {str(e)}")
            return None

    def stop_camera_stream(self, camera_id: str):
        """Stop camera streaming"""
        logger.info(f"Stopping camera stream for {camera_id}")
        
        # Signal stop event
        if camera_id in self.stop_events:
            self.stop_events[camera_id].set()
            del self.stop_events[camera_id]
        
        # Remove from active streams
        if camera_id in self.active_streams:
            del self.active_streams[camera_id]
        
        # Clean up thread reference
        if camera_id in self.stream_threads:
            del self.stream_threads[camera_id]

    def stop_all_streams(self):
        """Stop all active camera streams"""
        for camera_id in list(self.active_streams.keys()):
            self.stop_camera_stream(camera_id)