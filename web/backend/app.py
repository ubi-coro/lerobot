from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO
import logging
import os
import sys

# Add the parent directory to import LeRobot modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import API blueprints
from api.robot import bp as robot_bp, set_stream_service
from api.dataset import bp as dataset_bp
from api.policy import bp as policy_bp

# Import services
from services.stream_service import StreamService

app = Flask(__name__, static_folder='../frontend/dist')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize services
stream_service = StreamService(socketio)

# Set up service references
set_stream_service(stream_service)

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Register API blueprints
app.register_blueprint(robot_bp)
app.register_blueprint(dataset_bp)
app.register_blueprint(policy_bp)

# Serve frontend
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

# SocketIO event handlers for camera streaming
@socketio.on('connect')
def handle_connect():
    logger.info('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Client disconnected')
    
@socketio.on('start_camera_stream')
def handle_start_camera(data):
    camera_id = data.get('camera_id')
    fps = data.get('fps', 10)
    logger.info(f'Starting camera stream for {camera_id} at {fps} FPS')
    stream_service.start_camera_stream(camera_id, fps)

@socketio.on('stop_camera_stream')
def handle_stop_camera(data):
    camera_id = data.get('camera_id')
    logger.info(f'Stopping camera stream for {camera_id}')
    stream_service.stop_camera_stream(camera_id)

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='LeRobot Web Interface')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='Host to run the server on')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the server on')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    parser.add_argument('--mock', action='store_true', help='Use mock robot for testing')
    
    args = parser.parse_args()
    
    from api.robot import set_mock_mode
    if args.mock:
        set_mock_mode(True)
        logger.info("Running in MOCK mode (no robot hardware required)")
    
    socketio.run(app, host=args.host, port=args.port, debug=args.debug)