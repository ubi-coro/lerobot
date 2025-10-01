# backend/lerobot_adapter.py
from lerobot.robots.bi_viperx.config_bi_viperx import BiViperXConfig
from lerobot.robots.viperx.config_viperx import ViperXConfig
from lerobot.teleoperators.bi_widowx.config_bi_widowx import BiWidowXConfig
from lerobot.teleoperators.widowx.config_widowx import WidowXConfig
from lerobot.cameras.realsense.configuration_realsense import RealSenseCameraConfig
from config_models import RobotCfg, TeleopCfg

def to_lerobot_configs(robot: RobotCfg, teleop: TeleopCfg) -> tuple:
    """Konvertiere Pydantic-Modelle in LeRobot-Config-Objekte."""

    # Kameras konvertieren
    cameras = {}
    for name, cam in robot.cameras.items():
        cameras[name] = RealSenseCameraConfig(
            serial_number_or_name=cam.serial_number_or_name,
            width=cam.width,
            height=cam.height,
            fps=cam.fps
        )

    # Robot-Config
    if robot.type == "bi_viperx":
        robot_config = BiViperXConfig(
            id=robot.id,
            left_arm_port=robot.left_arm.port if robot.left_arm else None,
            right_arm_port=robot.right_arm.port if robot.right_arm else None,
            cameras=cameras
        )
        # Set calibration dirs if available
        if robot.left_arm and robot.left_arm.calibration_dir:
            robot_config.left_arm_calibration_dir = robot.left_arm.calibration_dir
        if robot.right_arm and robot.right_arm.calibration_dir:
            robot_config.right_arm_calibration_dir = robot.right_arm.calibration_dir
    else:  # viperx
        robot_config = ViperXConfig(
            id=robot.id,
            port=robot.port,
            calibration_dir=robot.calibration_dir,
            cameras=cameras
        )

    # Teleop-Config
    if teleop.type == "bi_widowx":
        teleop_config = BiWidowXConfig(
            id=teleop.id,
            left_arm_port=teleop.left_arm.port if teleop.left_arm else None,
            right_arm_port=teleop.right_arm.port if teleop.right_arm else None
        )
        # Set calibration dirs if available
        if teleop.left_arm and teleop.left_arm.calibration_dir:
            teleop_config.left_arm_calibration_dir = teleop.left_arm.calibration_dir
        if teleop.right_arm and teleop.right_arm.calibration_dir:
            teleop_config.right_arm_calibration_dir = teleop.right_arm.calibration_dir
    else:  # widowx
        teleop_config = WidowXConfig(
            id=teleop.id,
            port=teleop.port,
            calibration_dir=teleop.calibration_dir
        )

    return robot_config, teleop_config