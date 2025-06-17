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
ENHANCED ERROR HANDLING FOR DYNAMIXEL MOTORS

This module provides enhanced error detection and recovery for Dynamixel motors
to handle overload errors and communication failures more gracefully.

INTEGRATION NOTE: This is a new module that extends existing LeRobot functionality
without modifying core behavior. It can be safely disabled if needed.
"""

import logging
import time
from typing import Dict, List, Optional, Union


class DynamixelErrorMonitor:
    """
    Lightweight error monitoring for Dynamixel motors.
    
    DESIGN PRINCIPLE: Non-invasive monitoring that can be easily integrated
    into existing LeRobot robot classes without breaking current functionality.
    """
    
    # Dynamixel Hardware Error Status bits (from Dynamixel protocol)
    ERROR_CODES = {
        0x01: "Input Voltage Error",
        0x02: "Motor Hall Sensor Error", 
        0x04: "Overheating Error",
        0x08: "Motor Encoder Error",
        0x10: "Electrical Shock Error",
        0x20: "Overload Error",  # <-- This is the main issue we're addressing
        0x40: "Instruction Error",
        0x80: "Range Error"
    }
    
    def __init__(self, enable_monitoring: bool = True):
        """
        Initialize error monitor.
        
        Args:
            enable_monitoring: Can be set to False to disable all error handling
        """
        self.enable_monitoring = enable_monitoring
        self.logger = logging.getLogger(__name__)
        self.last_check_time = 0
        self.check_interval = 2.0  # Check every 2 seconds (conservative)
        
        if self.enable_monitoring:
            self.logger.info("Dynamixel error monitoring enabled")
        else:
            self.logger.info("Dynamixel error monitoring disabled")
    
    def check_motor_errors(self, motor_bus, motor_names: Optional[List[str]] = None) -> Dict[str, int]:
        """
        Check for hardware errors in specified motors.
        
        INTEGRATION: This method can be called from existing robot classes
        without modifying their core structure.
        
        Args:
            motor_bus: Existing DynamixelMotorsBus instance
            motor_names: List of motor names to check (None = check all)
            
        Returns:
            Dict mapping motor_name -> error_status (0 = no error)
        """
        if not self.enable_monitoring:
            return {}
            
        # Rate limiting to avoid performance impact
        current_time = time.time()
        if current_time - self.last_check_time < self.check_interval:
            return {}
        self.last_check_time = current_time
        
        errors = {}
        motors_to_check = motor_names or list(motor_bus.motors.keys())
        
        for motor_name in motors_to_check:
            try:
                # EXISTING LEROBOT PATTERN: Use existing motor_bus.read method
                error_status = motor_bus.read("Hardware_Error_Status", motor_name)
                
                if error_status != 0:
                    errors[motor_name] = error_status
                    
                    # Generate human-readable error description
                    error_descriptions = []
                    for bit, description in self.ERROR_CODES.items():
                        if error_status & bit:
                            error_descriptions.append(description)
                    
                    self.logger.warning(
                        f"Motor '{motor_name}' has hardware errors: {'; '.join(error_descriptions)} "
                        f"(Status: 0x{error_status:02X})"
                    )
                    
            except Exception as e:
                # CONSERVATIVE: Don't fail if error check fails
                self.logger.debug(f"Could not read error status for motor '{motor_name}': {e}")
                
        return errors
    
    def attempt_motor_recovery(self, motor_bus, motor_name: str) -> bool:
        """
        Attempt to recover a motor from error state.
        
        CONSERVATIVE APPROACH: Only attempts recovery if explicitly called.
        Does not automatically interfere with normal operation.
        
        Args:
            motor_bus: Existing DynamixelMotorsBus instance
            motor_name: Name of the motor to recover
            
        Returns:
            True if recovery successful, False otherwise
        """
        if not self.enable_monitoring:
            self.logger.info("Error recovery disabled")
            return False
            
        try:
            self.logger.info(f"Attempting recovery for motor '{motor_name}'")
            
            # STEP 1: Disable torque (EXISTING LEROBOT PATTERN)
            motor_bus.write("Torque_Enable", 0, motor_name)
            time.sleep(0.5)
            
            # STEP 2: Clear hardware error by rebooting motor
            motor_bus.write("Reboot", 1, motor_name)
            time.sleep(2.0)  # Wait for reboot to complete
            
            # STEP 3: Check if error is cleared
            error_status = motor_bus.read("Hardware_Error_Status", motor_name)
            
            if error_status == 0:
                self.logger.info(f"Motor '{motor_name}' successfully recovered")
                
                # STEP 4: Re-enable torque (EXISTING LEROBOT PATTERN)
                motor_bus.write("Torque_Enable", 1, motor_name)
                return True
            else:
                self.logger.warning(
                    f"Motor '{motor_name}' still has errors after recovery: 0x{error_status:02X}"
                )
                return False
                
        except Exception as e:
            self.logger.error(f"Recovery failed for motor '{motor_name}': {e}")
            return False
    
    def get_error_description(self, error_status: int) -> str:
        """
        Convert error status code to human-readable description.
        
        Args:
            error_status: Hardware error status register value
            
        Returns:
            Human-readable error description
        """
        if error_status == 0:
            return "No errors"
            
        descriptions = []
        for bit, description in self.ERROR_CODES.items():
            if error_status & bit:
                descriptions.append(description)
                
        return "; ".join(descriptions) if descriptions else f"Unknown error (0x{error_status:02X})"
    
    def is_overload_error(self, error_status: int) -> bool:
        """Check if error status indicates an overload condition."""
        return bool(error_status & 0x20)  # Bit 5 = Overload Error
