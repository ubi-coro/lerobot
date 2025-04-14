from flask import Blueprint, request, jsonify
import threading
import logging
import os
import glob

from services.robot_service import RobotService

use_mock = False

def set_mock_mode(mock_enabled):
    global use_mock, robot_service
    use_mock = mock_enabled
    robot_service = RobotService(use_mock=mock_enabled)

bp = Blueprint('robot', __name__, url_prefix='/api/robot')
robot_service = RobotService(use_mock=use_mock)
logger = logging.getLogger(__name__)

# Get reference to stream service from app later
stream_service = None

def set_stream_service(service):
    global stream_service
    stream_service = service
    stream_service.set_robot_service(robot_service)

@bp.route('/configs', methods=['GET'])
def get_robot_configs():
    """Get available robot configurations"""
    # Find all robot YAML files in the configs directory
    robot_dir = os.path.join('lerobot', 'configs', 'robot')
    config_files = glob.glob(os.path.join(robot_dir, '*.yaml'))
    
    configs = []
    for file_path in config_files:
        robot_name = os.path.basename(file_path).replace('.yaml', '')
        configs.append({
            'name': robot_name,
            'path': file_path
        })
    
    return jsonify(configs)

@bp.route('/connect', methods=['POST'])
def connect_robot():
    """Connect to the robot with the specified configuration"""
    data = request.json
    robot_config = data.get('robot_config')
    robot_overrides = data.get('robot_overrides')
    
    try:
        result = robot_service.connect(robot_config, robot_overrides)
        return jsonify({"status": "success", "data": result})
    except Exception as e:
        logger.error(f"Error connecting to robot: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/disconnect', methods=['POST'])
def disconnect_robot():
    """Disconnect from the robot"""
    try:
        # Stop all camera streams first
        if stream_service:
            stream_service.stop_all_streams()
            
        robot_service.disconnect()
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error disconnecting robot: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/status', methods=['GET'])
def get_robot_status():
    """Get current robot status"""
    status = robot_service.get_status()
    return jsonify(status)

@bp.route('/teleoperate/start', methods=['POST'])
def start_teleoperation():
    """Start robot teleoperation"""
    data = request.json
    fps = data.get('fps')
    display_cameras = data.get('display_cameras', False)  # Set to False for web interface
    
    try:
        robot_service.teleoperate(fps, display_cameras)
        return jsonify({"status": "success", "message": "Teleoperation started"})
    except Exception as e:
        logger.error(f"Error during teleoperation: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/teleoperate/stop', methods=['POST'])
def stop_teleoperation():
    """Stop robot teleoperation"""
    try:
        robot_service.stop_teleoperation()
        return jsonify({"status": "success", "message": "Teleoperation stopped"})
    except Exception as e:
        logger.error(f"Error stopping teleoperation: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/actions', methods=['POST'])
def send_action():
    """Send a single action to the robot"""
    data = request.json
    action = data.get('action')
    
    try:
        robot_service.send_action(action)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error sending action: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500