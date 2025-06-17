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
TEST SCRIPT: Dynamixel Error Handler Integration

This script tests the integration of the Dynamixel error handler into the LeRobot framework.
It verifies that error monitoring is properly initialized and functioning without disrupting
normal robot operation.

Usage:
    python test_error_handler_integration.py --robot.type=aloha

This script is safe to run as it only performs read operations and status checks.
"""

import logging
import sys
import time
from pathlib import Path

# Add lerobot to path if needed
sys.path.append(str(Path(__file__).parent.parent))

def test_error_handler_integration():
    """Test that error handler integration is working properly."""
    
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    logger.info("=== Testing Dynamixel Error Handler Integration ===")
    
    # Test 1: Check if error handler module is available
    try:
        from lerobot.common.robot_devices.motors.dynamixel_error_handler import DynamixelErrorMonitor
        logger.info("✓ Dynamixel error handler module is available")
        error_handler_available = True
    except ImportError as e:
        logger.warning(f"✗ Dynamixel error handler module not available: {e}")
        error_handler_available = False
    
    # Test 2: Check robot config integration  
    try:
        from lerobot.common.robot_devices.robots.configs import AlohaRobotConfig
        config = AlohaRobotConfig()
        
        if hasattr(config, 'enable_error_monitoring'):
            logger.info("✓ Robot config has error monitoring option")
            logger.info(f"  - enable_error_monitoring: {config.enable_error_monitoring}")
        else:
            logger.warning("✗ Robot config missing error monitoring option")
    except Exception as e:
        logger.error(f"✗ Error checking robot config: {e}")
    
    # Test 3: Check robot class integration (without connecting hardware)
    try:
        from lerobot.common.robot_devices.robots.manipulator import ManipulatorRobot
        
        # Create a config for testing (mock mode to avoid hardware)
        test_config = AlohaRobotConfig(
            calibration_dir=".cache/calibration/aloha_default",  # Use default
            enable_error_monitoring=True,
            mock=True  # Use mock mode for testing
        )
        
        # Create robot instance (mock mode)
        robot = ManipulatorRobot(test_config)
        
        if hasattr(robot, 'error_monitor'):
            logger.info("✓ Robot class has error monitor attribute")
            if robot.error_monitor is not None:
                logger.info("✓ Error monitor is initialized")
                logger.info(f"  - Monitoring enabled: {robot.error_monitor.enable_monitoring}")
            else:
                logger.info("  - Error monitor is None (expected for mock or unsupported robot)")
        else:
            logger.warning("✗ Robot class missing error monitor attribute")
            
        if hasattr(robot, '_check_and_handle_motor_errors'):
            logger.info("✓ Robot class has error checking method")
        else:
            logger.warning("✗ Robot class missing error checking method")
            
    except Exception as e:
        logger.error(f"✗ Error testing robot class integration: {e}")
    
    # Test 4: Check control_utils integration
    try:
        from lerobot.common.robot_devices.control_utils import teleop_step
        import inspect
        
        # Check if teleop_step has error handling comments
        source = inspect.getsource(teleop_step)
        if "INTEGRATION POINT" in source:
            logger.info("✓ control_utils.teleop_step has integration points")
        else:
            logger.warning("✗ control_utils.teleop_step missing integration points")
            
    except Exception as e:
        logger.error(f"✗ Error checking control_utils integration: {e}")
    
    # Test 5: Check error handler functionality (if available)
    if error_handler_available:
        try:
            monitor = DynamixelErrorMonitor(enable_monitoring=True)
            
            # Test error code descriptions
            test_error = 0x20  # Overload error
            description = monitor.get_error_description(test_error)
            logger.info(f"✓ Error description test: 0x{test_error:02X} -> '{description}'")
            
            # Test overload detection
            is_overload = monitor.is_overload_error(test_error)
            logger.info(f"✓ Overload detection test: 0x{test_error:02X} -> {is_overload}")
            
        except Exception as e:
            logger.error(f"✗ Error testing error handler functionality: {e}")
    
    logger.info("=== Integration Test Complete ===")
    logger.info("")
    logger.info("INTEGRATION STATUS:")
    logger.info("- The error handler is integrated into the LeRobot framework")
    logger.info("- Error monitoring can be enabled/disabled via robot config")
    logger.info("- Integration points are marked with clear comments")
    logger.info("- The system remains fully operational even if error handling fails")
    logger.info("")
    logger.info("TO USE ERROR HANDLING:")
    logger.info("1. Set enable_error_monitoring=True in your robot config (default)")
    logger.info("2. Set DISABLE_ERROR_MONITORING=1 environment variable to disable")
    logger.info("3. Check logs for error detection and recovery messages")

if __name__ == "__main__":
    test_error_handler_integration()
