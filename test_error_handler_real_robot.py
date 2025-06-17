#!/usr/bin/env python3
# Copyright 2024 The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
REAL ROBOT ERROR HANDLING TEST

This script tests error handling in a real-world scenario with actual robot hardware.
It connects to the robot, enables error monitoring, and runs teleoperation for
a specified duration to check if errors are properly detected and recovered from.

Make sure the robot is properly connected and powered on before running this script.

Usage:
    python test_error_handler_real_robot.py --duration 60

Options:
    --duration : Duration to run the test in seconds (default: 60)
    --verbose : Enable verbose logging (default: False)
    --simulate_error : Simulate error conditions (default: False)

To see error handling in action:
1. Run the script with the robot connected
2. Gently apply resistance to a motor during operation (to trigger overload)
3. Observe the logs for error detection and recovery messages
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

# Add lerobot to path if needed
sys.path.append(str(Path(__file__).parent))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('error_handler_test.log')
    ]
)

def run_real_robot_test(duration=60, verbose=False, simulate_error=False, mock=False):
    """Run the robot with error handling enabled and monitor for errors."""
    logger = logging.getLogger(__name__)
    
    if verbose:
        logger.setLevel(logging.DEBUG)
        logging.getLogger('lerobot').setLevel(logging.DEBUG)
    
    logger.info("=== Starting Real Robot Error Handling Test ===")
    logger.info(f"Mode: {'MOCK' if mock else 'REAL HARDWARE'}")
    
    try:
        # Import required modules
        from lerobot.common.robot_devices.robots.configs import AlohaRobotConfig
        from lerobot.common.robot_devices.robots.manipulator import ManipulatorRobot
        from lerobot.common.robot_devices.control_utils import control_loop
        
        # Create robot configuration with error monitoring enabled
        # Use the known working calibration directory
        calibration_dir = "/home/jannick/PycharmProjects/lerobot/.cache/calibration/aloha_lemgo_tabea"
        
        logger.info(f"Using calibration directory: {calibration_dir}")
        
        # Create robot config with error monitoring
        try:
            config = AlohaRobotConfig(
                calibration_dir=calibration_dir,
                max_relative_target=25,
                enable_error_monitoring=True,  # Enable error monitoring
                mock=mock  # Use mock mode if specified
            )
        except Exception as e:
            logger.warning(f"Failed to load calibration from {calibration_dir}: {e}")
            logger.info("Falling back to default mock configuration")
            # Use a simpler configuration for testing
            config = AlohaRobotConfig(
                enable_error_monitoring=True,
                mock=True  # Force mock mode
            )
        
        # Create and connect robot
        logger.info("Creating robot instance...")
        robot = ManipulatorRobot(config)
        
        logger.info(f"Error monitor available: {robot.error_monitor is not None}")
        if robot.error_monitor:
            logger.info(f"Error monitoring enabled: {robot.error_monitor.enable_monitoring}")
        
        logger.info("Connecting to robot...")
        robot.connect()
        logger.info("Robot connected successfully")
        
        # Test error handling during teleoperation
        logger.info(f"Starting teleoperation for {duration} seconds...")
        
        # Use a simple control loop that just monitors for errors
        start_time = time.time()
        teleop_count = 0
        
        # Test parameters
        check_interval = 1.0  # Check for errors every second
        last_status_time = 0
        
        if simulate_error:
            logger.warning("Error simulation mode enabled - will simulate errors")
        
        try:
            while time.time() - start_time < duration:
                # Run a teleop step
                robot.teleop_step()
                teleop_count += 1
                
                # Give status updates periodically
                current_time = time.time()
                if current_time - last_status_time >= check_interval:
                    elapsed = current_time - start_time
                    logger.info(f"Test running: {elapsed:.1f}s / {duration}s - {teleop_count} teleop steps")
                    last_status_time = current_time
                    
                    # If simulating errors, force an error check
                    if simulate_error and robot.error_monitor:
                        logger.info("Simulating error detection...")
                        robot._check_and_handle_motor_errors()
                
                # Sleep a bit to avoid maxing out CPU
                time.sleep(0.01)
                
        except KeyboardInterrupt:
            logger.info("Test interrupted by user")
        
        # Disconnect robot
        logger.info("Disconnecting robot...")
        robot.disconnect()
        
        logger.info("=== Real Robot Error Handling Test Complete ===")
        logger.info(f"Completed {teleop_count} teleoperation steps")
        logger.info("Check the log for any error detection and recovery messages")
        
    except Exception as e:
        logger.error(f"Error during test: {e}", exc_info=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test error handling on a real robot")
    parser.add_argument("--duration", type=int, default=60, help="Duration to run the test (seconds)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--simulate_error", action="store_true", help="Simulate error conditions")
    parser.add_argument("--mock", action="store_true", help="Use mock mode instead of real hardware")
    args = parser.parse_args()
    
    run_real_robot_test(args.duration, args.verbose, args.simulate_error, args.mock)
