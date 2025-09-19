#!/usr/bin/env python

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
Tests for Dynamixel Error Handler.

This file contains unit and integration tests for the DynamixelErrorMonitor class.

Example of running tests:
```bash
pytest -sx tests/motors/test_dynamixel_error_handler.py
```
"""

import time
import pytest
import logging
from unittest.mock import MagicMock, patch

from lerobot.common.robot_devices.motors.dynamixel_error_handler import DynamixelErrorMonitor


# Create simple mocks for testing
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
        elif register == "Reboot":
            self.motors[motor_name].rebooted = True
            # Clear error after reboot for overload errors
            if self.motors[motor_name].error_code == 0x20:  # Overload
                self.motors[motor_name].error_code = 0


@pytest.fixture
def error_monitor():
    """Create a DynamixelErrorMonitor with monitoring enabled"""
    return DynamixelErrorMonitor(enable_monitoring=True)


@pytest.fixture
def error_bus():
    """Create a MockMotorBus with simulated errors"""
    return MockMotorBus(simulate_errors=True)


@pytest.fixture
def normal_bus():
    """Create a MockMotorBus with no errors"""
    return MockMotorBus(simulate_errors=False)


class TestDynamixelErrorMonitor:
    """Test suite for DynamixelErrorMonitor"""

    def test_init_with_monitoring_enabled(self):
        """Test initialization with monitoring enabled"""
        monitor = DynamixelErrorMonitor(enable_monitoring=True)
        assert monitor.enable_monitoring == True
        
    def test_init_with_monitoring_disabled(self):
        """Test initialization with monitoring disabled"""
        monitor = DynamixelErrorMonitor(enable_monitoring=False)
        assert monitor.enable_monitoring == False

    def test_error_detection(self, error_monitor, error_bus):
        """Test that errors are correctly detected"""
        # Reset last check time to ensure check happens
        error_monitor.last_check_time = 0
        
        # Check for errors
        errors = error_monitor.check_motor_errors(error_bus)
        
        # Should find errors on shoulder and elbow
        assert "shoulder" in errors
        assert errors["shoulder"] == 0x20  # Overload error
        assert "elbow" in errors
        assert errors["elbow"] == 0x04  # Overheating error
        assert len(errors) == 2  # No other errors

    def test_rate_limiting(self, error_monitor, error_bus):
        """Test that rate limiting prevents frequent checks"""
        # First check - should detect errors
        error_monitor.last_check_time = 0
        first_check = error_monitor.check_motor_errors(error_bus)
        assert len(first_check) > 0
        
        # Immediate second check - should be empty due to rate limiting
        second_check = error_monitor.check_motor_errors(error_bus)
        assert len(second_check) == 0
        
        # After forcing check interval to elapse
        error_monitor.last_check_time = time.time() - error_monitor.check_interval - 1
        third_check = error_monitor.check_motor_errors(error_bus)
        assert len(third_check) > 0

    def test_overload_detection(self, error_monitor):
        """Test correct identification of overload errors"""
        # Overload is 0x20 (bit 5)
        assert error_monitor.is_overload_error(0x20) == True
        assert error_monitor.is_overload_error(0x30) == True  # Overload + another error
        assert error_monitor.is_overload_error(0x01) == False  # Not overload
        assert error_monitor.is_overload_error(0) == False  # No error

    def test_recovery_for_overload_errors(self, error_monitor, error_bus):
        """Test recovery process for overload errors"""
        # Attempt recovery for shoulder (which has overload error)
        success = error_monitor.attempt_motor_recovery(error_bus, "shoulder")
        
        # Should succeed and clear error
        assert success == True
        assert error_bus.motors["shoulder"].error_code == 0
        assert error_bus.motors["shoulder"].rebooted == True
        assert error_bus.motors["shoulder"].torque_enabled == True

    def test_no_recovery_for_non_overload_errors(self, error_monitor, error_bus):
        """Test that non-overload errors aren't automatically recovered"""
        # Attempt recovery for elbow (which has overheating error)
        success = error_monitor.attempt_motor_recovery(error_bus, "elbow")
        
        # Should fail and not clear error
        assert success == False
        assert error_bus.motors["elbow"].error_code == 0x04
        assert error_bus.motors["elbow"].rebooted == True  # Still attempts reboot
        # Note: The recovery process disables torque even for non-overload errors
        # But it doesn't re-enable it if recovery fails
        assert error_bus.motors["elbow"].torque_enabled == False

    def test_error_description(self, error_monitor):
        """Test generation of human-readable error descriptions"""
        # Test individual error codes
        assert "Overload Error" in error_monitor.get_error_description(0x20)
        assert "Overheating Error" in error_monitor.get_error_description(0x04)
        assert "Input Voltage Error" in error_monitor.get_error_description(0x01)
        
        # Test multiple errors
        multi_error_desc = error_monitor.get_error_description(0x24)  # Overload + Overheating
        assert "Overload Error" in multi_error_desc
        assert "Overheating Error" in multi_error_desc
        
        # No errors
        assert error_monitor.get_error_description(0) == "No errors"

    def test_monitoring_disabled_no_checks(self, error_bus):
        """Test that no checking occurs when monitoring is disabled"""
        disabled_monitor = DynamixelErrorMonitor(enable_monitoring=False)
        errors = disabled_monitor.check_motor_errors(error_bus)
        assert len(errors) == 0
        
        # Even when forcing last_check_time to 0
        disabled_monitor.last_check_time = 0
        errors = disabled_monitor.check_motor_errors(error_bus)
        assert len(errors) == 0

    def test_integration_with_robot_structure(self, error_monitor):
        """Test integration with robot class structure"""
        # Setup mock robot arms structure
        leader_arms = {
            "left": MockMotorBus(simulate_errors=False),
            "right": MockMotorBus(simulate_errors=False)
        }
        follower_arms = {
            "left": MockMotorBus(simulate_errors=True),
            "right": MockMotorBus(simulate_errors=False)
        }
        
        # Force reset of last check time to ensure check happens
        error_monitor.last_check_time = 0
        
        # Temporarily patch the check_motor_errors method to disable rate limiting
        original_check = error_monitor.check_motor_errors
        def mock_check(motor_bus, motor_names=None):
            # Skip rate limiting for this test
            error_monitor.last_check_time = 0
            return original_check(motor_bus, motor_names)
        error_monitor.check_motor_errors = mock_check
        
        # Check for errors in all arms
        all_errors = {}
        
        # Check leader arms
        for name, motor_bus in leader_arms.items():
            errors = error_monitor.check_motor_errors(motor_bus)
            if errors:
                all_errors[f"leader_{name}"] = errors
                
        # Check follower arms
        for name, motor_bus in follower_arms.items():
            errors = error_monitor.check_motor_errors(motor_bus)
            if errors:
                all_errors[f"follower_{name}"] = errors
        
        # Should find errors only in follower_left
        assert "follower_left" in all_errors
        assert "leader_left" not in all_errors
        assert "leader_right" not in all_errors
        assert "follower_right" not in all_errors
        
        # Specifically, should find shoulder and elbow errors
        assert "shoulder" in all_errors["follower_left"]
        assert all_errors["follower_left"]["shoulder"] == 0x20
        assert "elbow" in all_errors["follower_left"]
        assert all_errors["follower_left"]["elbow"] == 0x04


if __name__ == "__main__":
    pytest.main()
