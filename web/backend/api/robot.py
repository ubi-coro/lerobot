from flask import Blueprint, request, jsonify
import logging

from services.robot_service import RobotService

bp = Blueprint('robot', __name__, url_prefix='/api/robot')
logger = logging.getLogger(__name__)

# Initialize with your preferred mock setting
robot_service = RobotService(use_mock=False)

@bp.route('/configs', methods=['GET'])
def get_robot_configs():
    """Get available robot configurations"""
    configs = [
        {
            'name': 'Aloha Robot',
            'path': 'aloha_robot',
            'type': 'aloha'
        }
    ]
    
    logger.info(f"Sending robot configs: {configs}")
    return jsonify({"status": "success", "data": configs})

@bp.route('/connect', methods=['POST'])
def connect_aloha():
    """Connect to ALOHA robot"""
    data = request.json or {}
    operation_mode = data.get('operation_mode', 'bimanual')
    
    try:
        # Prepare overrides based on operation mode
        overrides = []
        if operation_mode == 'right_only':
            overrides = ['~leader_arms.left', '~follower_arms.left']
        elif operation_mode == 'left_only':
            overrides = ['~leader_arms.right', '~follower_arms.right']
        elif operation_mode == 'bimanual':
            overrides = []  # No exclusions for bimanual
        
        result = robot_service.connect_aloha(overrides)
        return jsonify({"status": "success", "data": result})
        
    except Exception as e:
        logger.error(f"Error connecting to ALOHA robot: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/disconnect', methods=['POST'])
def disconnect_robot():
    """Disconnect from the robot"""
    try:
        robot_service.disconnect()
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error disconnecting robot: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/status', methods=['GET'])
def get_robot_status():
    """Get current robot status"""
    status = robot_service.get_status()
    logger.info(f"Sending robot status: {status}")
    return jsonify({
        "status": "success",
        "data": status
    })

@bp.route('/teleoperate/start', methods=['POST'])
def start_teleoperation():
    """Start ALOHA robot teleoperation"""
    data = request.json or {}
    fps = data.get('fps', 30)
    show_cameras = data.get('show_cameras', True)  # Add this line
    
    try:
        robot_service.start_teleoperation(fps=fps, show_cameras=show_cameras)  # Pass both parameters
        return jsonify({"status": "success", "message": "ALOHA teleoperation started"})
    except Exception as e:
        logger.error(f"Error starting ALOHA teleoperation: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/teleoperate/stop', methods=['POST'])
def stop_teleoperation():
    """Stop ALOHA robot teleoperation"""
    try:
        robot_service.stop_teleoperation()
        return jsonify({"status": "success", "message": "ALOHA teleoperation stopped"})
    except Exception as e:
        logger.error(f"Error stopping ALOHA teleoperation: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/teleoperate/start-advanced', methods=['POST'])
def start_teleoperation_advanced():
    """Start ALOHA robot teleoperation with advanced configuration"""
    data = request.json or {}
    
    try:
        # Extract advanced configuration
        config = {
            'fps': data.get('fps', 30),
            'show_cameras': data.get('show_cameras', True),
            'max_relative_target': data.get('max_relative_target', 25),
            'operation_mode': data.get('operation_mode', 'bimanual'),
            'enable_safe_shutdown': data.get('enable_safe_shutdown', True),
            'moving_time': data.get('moving_time', 0.1),
            'teleop_time_limit': data.get('teleop_time_limit'),
            'performance_monitoring': data.get('performance_monitoring', False),
            'debug_level': data.get('debug_level', 'INFO')
        }
        
        robot_service.start_teleoperation_advanced(config)
        return jsonify({
            "status": "success", 
            "message": "Advanced ALOHA teleoperation started",
            "config": config
        })
    except Exception as e:
        logger.error(f"Error starting advanced ALOHA teleoperation: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/teleoperate/emergency-stop', methods=['POST'])
def emergency_stop():
    """Emergency stop for teleoperation"""
    try:
        robot_service.emergency_stop()
        return jsonify({"status": "success", "message": "Emergency stop activated"})
    except Exception as e:
        logger.error(f"Error during emergency stop: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/teleoperate/performance', methods=['GET'])
def get_performance_metrics():
    """Get current teleoperation performance metrics"""
    try:
        metrics = robot_service.get_performance_metrics()
        return jsonify({
            "status": "success",
            "data": metrics
        })
    except Exception as e:
        logger.error(f"Error getting performance metrics: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/robot/safe-position', methods=['POST'])
def move_to_safe_position():
    """Move robot to safe position"""
    data = request.json or {}
    
    try:
        config = {
            'arms': data.get('arms'),  # None for all arms, list for specific arms
            'timeout_s': data.get('timeout_s', 10.0),
            'speed_factor': data.get('speed_factor', 0.3),
            'display_data': data.get('display_data', False)
        }
        
        result = robot_service.move_to_safe_position(config)
        return jsonify({
            "status": "success",
            "message": "Robot moved to safe position",
            "data": result
        })
    except Exception as e:
        logger.error(f"Error moving to safe position: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Add streaming function if needed
def set_stream_service(stream_service):
    """Set the stream service for camera functionality"""
    global _stream_service
    _stream_service = stream_service