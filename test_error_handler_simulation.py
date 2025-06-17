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
SIMULATE MOTOR ERRORS DURING TELEOPERATION

This script simulates motor errors during teleoperation to test error detection
and recovery without needing to physically stress the robot.

Usage:
    python test_error_handler_simulation.py

Options:
    --duration : Duration to run the test in seconds (default: 60)
    --error_type : Type of error to simulate ('overload', 'input_voltage', 'all')
    --interval : How often to simulate errors in seconds (default: 10)

This script uses a mock mode to avoid hardware interaction but allows testing
of the error handling pathways.
"""

import argparse
import logging
import os
import sys
import time
import random
from pathlib import Path
from unittest.mock import patch

# Add lerobot to path if needed
sys.path.append(str(Path(__file__).parent))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('error_simulation_test.log')
    ]
)

def run_error_simulation_test(duration=60, error_type='overload', interval=10):
    """Run a simulation test with injected motor errors."""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    logger.info("=== Starting Error Simulation Test ===")
    logger.info(f"Duration: {duration}s, Error Type: {error_type}, Interval: {interval}s")
    
    try:
        # Import required modules
        from lerobot.common.robot_devices.robots.configs import AlohaRobotConfig
        from lerobot.common.robot_devices.robots.manipulator import ManipulatorRobot
        from lerobot.common.robot_devices.motors.dynamixel_error_handler import DynamixelErrorMonitor
        
        # Create robot configuration with error monitoring enabled
        # In mock mode, the calibration directory doesn't matter
        config = AlohaRobotConfig(
            calibration_dir=".cache/calibration/aloha_default",  # This path won't be used in mock mode
            max_relative_target=25,
            enable_error_monitoring=True,
            mock=True  # Use mock mode for simulation
        )
        
        # Create and connect robot
        logger.info("Creating robot instance in mock mode...")
        robot = ManipulatorRobot(config)
        
        # Verify error monitoring is enabled
        if robot.error_monitor:
            logger.info(f"Error monitoring enabled: {robot.error_monitor.enable_monitoring}")
        else:
            raise RuntimeError("Error monitor not initialized")
            
        logger.info("Connecting to robot...")
        robot.connect()
        logger.info("Robot connected successfully (mock mode)")
        
        # Error codes for simulation
        ERROR_CODES = {
            'overload': 0x20,         # Overload error only
            'input_voltage': 0x01,    # Input voltage error only  
            'multiple': 0x24,         # Overload + overheating
            'all': 0xFF               # All error bits set
        }
        
        error_code = ERROR_CODES.get(error_type, 0x20)  # Default to overload
        
        # Simulation parameters
        start_time = time.time()
        teleop_count = 0
        last_error_time = 0
        last_status_time = 0
        check_interval = 1.0
        
        # Patch the check_motor_errors method to simulate errors
        original_check_method = robot.error_monitor.check_motor_errors
        
        def simulate_error_in_random_motor(motor_bus, motor_names=None):
            """Simulate an error in a random motor at specified intervals."""
            current_time = time.time()
            elapsed = current_time - start_time
            
            # Only simulate errors at the specified interval
            if current_time - last_error_time >= interval:
                logger.info(f"Simulating {error_type} error at {elapsed:.1f}s")
                
                # Pick a random arm and motor
                arm_type = random.choice(['leader', 'follower'])
                arm_side = random.choice(['left', 'right'])
                joint_type = random.choice(['shoulder', 'upper_arm', 'forearm', 'wrist', 'hand'])
                
                motor_key = f"{arm_type}_{arm_side}.{joint_type}"
                logger.info(f"Simulating error on motor: {motor_key}")
                
                # Return simulated errors
                return {motor_key: error_code}
            
            # No errors most of the time
            return {}
        
        # Use monkey patching to simulate errors
        robot.error_monitor.check_motor_errors = simulate_error_in_random_motor
        
        try:
            logger.info(f"Starting teleoperation simulation for {duration} seconds...")
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
                    
                    # Force an error check/recovery occasionally
                    if elapsed % interval < 0.1:
                        logger.info("Forcing error check...")
                        last_error_time = current_time
                        robot._check_and_handle_motor_errors()
                
                # Sleep a bit to avoid maxing out CPU
                time.sleep(0.01)
                
        except KeyboardInterrupt:
            logger.info("Test interrupted by user")
            
        # Restore original method
        robot.error_monitor.check_motor_errors = original_check_method
        
        # Disconnect robot
        logger.info("Disconnecting robot...")
        robot.disconnect()
        
        logger.info("=== Error Simulation Test Complete ===")
        logger.info(f"Completed {teleop_count} teleoperation steps")
        logger.info("Check the log for error detection and recovery messages")
        
    except Exception as e:
        logger.error(f"Error during test: {e}", exc_info=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulate motor errors during teleoperation")
    parser.add_argument("--duration", type=int, default=60, help="Duration to run the test (seconds)")
    parser.add_argument("--error_type", default='overload', choices=['overload', 'input_voltage', 'multiple', 'all'],
                        help="Type of error to simulate")
    parser.add_argument("--interval", type=int, default=10, help="How often to simulate errors (seconds)")
    args = parser.parse_args()
    
    run_error_simulation_test(args.duration, args.error_type, args.interval)
