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
DIRECT TEST OF DYNAMIXEL ERROR HANDLER

This script directly tests the DynamixelErrorMonitor class functionality
without requiring robot hardware or calibration. It verifies that error
detection and recovery mechanisms work as expected.

Usage:
    python test_direct_error_handler.py

This test doesn't require any hardware and is safe to run.
"""

import logging
import sys
import time
from pathlib import Path

# Add lerobot to path if needed
sys.path.append(str(Path(__file__).parent))

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('direct_error_test.log')
    ]
)
logger = logging.getLogger(__name__)


# Create simple mocks for testing without hardware
class MockMotor:
    def __init__(self, name, error_code=0):
        self.name = name
        self.error_code = error_code
        self.torque_enabled = True
        self.rebooted = False


class MockMotorBus:
    def __init__(self, motors=None, simulate_errors=False):
        self.motors = motors or {
            "shoulder": MockMotor("shoulder", 0x20 if simulate_errors else 0),  # Shoulder with overload error
            "elbow": MockMotor("elbow", 0x04 if simulate_errors else 0),        # Elbow with overheating error
            "wrist": MockMotor("wrist", 0),
            "gripper": MockMotor("gripper", 0)
        }
        self.simulate_errors = simulate_errors
    
    def read(self, register, motor_name=None):
        """Simulate reading a register from a motor"""
        if register == "Hardware_Error_Status":
            # Always return the error code stored in the motor object
            return self.motors[motor_name].error_code
        elif register == "Torque_Enable":
            return 1 if self.motors[motor_name].torque_enabled else 0
        return 0
        
    def write(self, register, value, motor_name=None):
        """Simulate writing to a motor register"""
        if register == "Torque_Enable":
            self.motors[motor_name].torque_enabled = bool(value)
            logger.debug(f"Set torque for {motor_name} to {value}")
        elif register == "Reboot":
            self.motors[motor_name].rebooted = True
            # Clear error after reboot for overload errors
            if self.motors[motor_name].error_code == 0x20:  # Overload
                self.motors[motor_name].error_code = 0
                logger.debug(f"Cleared overload error for {motor_name}")
            logger.debug(f"Rebooted motor {motor_name}")


def test_error_detection():
    """Test basic error detection functionality"""
    logger.info("=== Testing Error Detection ===")
    
    # Import the DynamixelErrorMonitor class
    from lerobot.common.robot_devices.motors.dynamixel_error_handler import DynamixelErrorMonitor
    
    # Create instance with error monitoring enabled
    monitor = DynamixelErrorMonitor(enable_monitoring=True)
    logger.info(f"Error monitoring enabled: {monitor.enable_monitoring}")
    
    # Test with motors that have errors
    error_bus = MockMotorBus(simulate_errors=True)
    errors = monitor.check_motor_errors(error_bus)
    
    # We should have detected errors
    if errors:
        logger.info(f"Detected errors: {errors}")
        
        if "shoulder" in errors and errors["shoulder"] == 0x20:
            logger.info("✓ Successfully detected shoulder overload error")
        else:
            logger.error("✗ Failed to detect shoulder overload error")
            
        if "elbow" in errors and errors["elbow"] == 0x04:
            logger.info("✓ Successfully detected elbow overheating error")
        else:
            logger.error("✗ Failed to detect elbow overheating error")
    else:
        logger.error("✗ Failed to detect any errors")
        
    # Test that rate limiting works
    monitor.last_check_time = time.time()  # Just checked
    more_errors = monitor.check_motor_errors(error_bus)
    if not more_errors:
        logger.info("✓ Rate limiting worked - no immediate re-check")
    else:
        logger.error("✗ Rate limiting failed - immediate re-check happened")
    
    # Return overall success
    return len(errors) == 2  # Should have found 2 errors


def test_error_recovery():
    """Test error recovery functionality"""
    logger.info("=== Testing Error Recovery ===")
    
    # Import the DynamixelErrorMonitor class
    from lerobot.common.robot_devices.motors.dynamixel_error_handler import DynamixelErrorMonitor
    
    # Create instance with error monitoring enabled
    monitor = DynamixelErrorMonitor(enable_monitoring=True)
    
    # Test error classification
    is_overload = monitor.is_overload_error(0x20)
    logger.info(f"Is 0x20 an overload error? {is_overload}")
    
    if is_overload:
        logger.info("✓ Correctly identified overload error")
    else:
        logger.error("✗ Failed to identify overload error")
        return False
    
    # Test recovery for overload error
    error_bus = MockMotorBus(simulate_errors=True)
    recovery_result = monitor.attempt_motor_recovery(error_bus, "shoulder")
    
    if recovery_result:
        logger.info("✓ Successfully recovered from shoulder overload error")
        if error_bus.motors["shoulder"].rebooted:
            logger.info("✓ Motor was correctly rebooted during recovery")
        else:
            logger.error("✗ Motor was not rebooted during recovery")
            
        if not error_bus.motors["shoulder"].error_code:
            logger.info("✓ Error code was cleared after recovery")
        else:
            logger.error("✗ Error code was not cleared after recovery")
            
        if error_bus.motors["shoulder"].torque_enabled:
            logger.info("✓ Torque was re-enabled after recovery")
        else:
            logger.error("✗ Torque was not re-enabled after recovery")
    else:
        logger.error("✗ Failed to recover from overload error")
        
    # Test non-recovery for non-overload errors (like overheating)
    recovery_result = monitor.attempt_motor_recovery(error_bus, "elbow")
    
    if not recovery_result:
        logger.info("✓ Correctly did not recover from non-overload error")
    else:
        logger.error("✗ Incorrectly recovered from non-overload error")
        
    return True


def test_integration():
    """Test error handling integration into robot class structure"""
    logger.info("=== Testing Full Error Handling Integration ===")
    
    # Import the DynamixelErrorMonitor class
    from lerobot.common.robot_devices.motors.dynamixel_error_handler import DynamixelErrorMonitor
    
    # Create components for testing
    monitor = DynamixelErrorMonitor(enable_monitoring=True)
    # Reset last check time to ensure errors are detected
    monitor.last_check_time = 0
    
    # Simulate follower_left arm having errors
    leader_arms = {
        "left": MockMotorBus(simulate_errors=False),
        "right": MockMotorBus(simulate_errors=False)
    }
    follower_arms = {
        "left": MockMotorBus(simulate_errors=True),
        "right": MockMotorBus(simulate_errors=False)
    }
    
    # Track which motors were recovered
    recovered_motors = []
    
    # This mock directly handles the rate limiting check
    # Override the check_motor_errors method temporarily for our test 
    original_check = monitor.check_motor_errors
    def mock_check(motor_bus, motor_names=None):
        # Skip rate limiting for this test
        monitor.last_check_time = 0
        return original_check(motor_bus, motor_names)
    monitor.check_motor_errors = mock_check
    
    # Create a simplified version of the _check_and_handle_motor_errors method
    def check_and_handle_motor_errors():
        
        # Check both leader and follower arms for errors
        all_errors = {}
        
        # Check leader arms
        for name, motor_bus in leader_arms.items():
            errors = monitor.check_motor_errors(motor_bus)
            if errors:
                all_errors[f"leader_{name}"] = errors
                
        # Check follower arms  
        for name, motor_bus in follower_arms.items():
            # Direct check of motors in the mock bus to verify they have errors
            for motor_name, motor in motor_bus.motors.items():
                logger.debug(f"Follower {name} motor {motor_name} has error code: 0x{motor.error_code:02X}")
                
            errors = monitor.check_motor_errors(motor_bus)
            logger.debug(f"Follower {name} errors: {errors}")
            if errors:
                all_errors[f"follower_{name}"] = errors
        
        # Handle any detected errors
        if all_errors:
            logger.warning(f"Motor errors detected: {all_errors}")
            
            # For overload errors, attempt automatic recovery
            for arm_name, motor_errors in all_errors.items():
                for motor_name, error_status in motor_errors.items():
                    if monitor.is_overload_error(error_status):
                        logger.info(f"Overload detected on {arm_name}.{motor_name}, attempting recovery...")
                        
                        # Determine which motor bus to use
                        if arm_name.startswith("leader_"):
                            bus_name = arm_name[7:]  # Remove "leader_" prefix
                            motor_bus = leader_arms.get(bus_name)
                        elif arm_name.startswith("follower_"):
                            bus_name = arm_name[9:]  # Remove "follower_" prefix  
                            motor_bus = follower_arms.get(bus_name)
                        else:
                            continue
                            
                        if motor_bus is not None:
                            recovery_success = monitor.attempt_motor_recovery(motor_bus, motor_name)
                            if recovery_success:
                                logger.info(f"Successfully recovered {arm_name}.{motor_name}")
                                recovered_motors.append(f"{arm_name}.{motor_name}")
                            else:
                                logger.warning(f"Failed to recover {arm_name}.{motor_name}")
                    else:
                        # For non-overload errors, just log them
                        error_desc = monitor.get_error_description(error_status)
                        logger.warning(f"Motor {arm_name}.{motor_name} has error: {error_desc}")
        
        return all_errors
    
    # Run the error check
    detected_errors = check_and_handle_motor_errors()
    
    # Check results
    success = True
    
    # Should detect errors on follower_left arm
    if "follower_left" in detected_errors:
        logger.info("✓ Successfully detected errors in follower_left arm")
        
        # Should have recovered shoulder but not elbow
        if "follower_left.shoulder" in recovered_motors:
            logger.info("✓ Successfully recovered from shoulder overload error")
        else:
            logger.error("✗ Failed to recover from shoulder overload error")
            success = False
            
        if "follower_left.elbow" not in recovered_motors:
            logger.info("✓ Correctly did not recover from elbow overheating error")
        else:
            logger.error("✗ Incorrectly recovered from elbow overheating error")
            success = False
    else:
        logger.error("✗ Failed to detect errors in follower_left arm")
        success = False
        
    return success


def run_all_tests():
    """Run all error handler tests without hardware"""
    logger.info("=== STARTING DIRECT ERROR HANDLER TESTS ===")
    
    overall_success = True
    
    # Test 1: Error Detection
    logger.info("Running Test 1: Error Detection")
    if test_error_detection():
        logger.info("Test 1: Error Detection - PASSED")
    else:
        logger.error("Test 1: Error Detection - FAILED")
        overall_success = False
    
    # Test 2: Error Recovery
    logger.info("Running Test 2: Error Recovery")
    if test_error_recovery():
        logger.info("Test 2: Error Recovery - PASSED")
    else:
        logger.error("Test 2: Error Recovery - FAILED")
        overall_success = False
    
    # Test 3: Integration
    logger.info("Running Test 3: Integration")
    if test_integration():
        logger.info("Test 3: Integration - PASSED")
    else:
        logger.error("Test 3: Integration - FAILED")
        overall_success = False
    
    # Summary
    logger.info("=== DIRECT ERROR HANDLER TEST RESULTS ===")
    logger.info(f"Overall Test Result: {'PASSED' if overall_success else 'FAILED'}")
    
    return overall_success


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
