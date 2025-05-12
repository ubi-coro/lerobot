from lerobot.common.robot_devices.robots.configs import AlohaRobotConfig

def get_robot_config():
    """Get Aloha robot configuration with default settings"""
    return AlohaRobotConfig(
        calibration_dir=".cache/calibration/aloha_lemgo_tabea",  # Use your existing path
        max_relative_target=25,
        moving_time=0.1,
        mock=False
    )