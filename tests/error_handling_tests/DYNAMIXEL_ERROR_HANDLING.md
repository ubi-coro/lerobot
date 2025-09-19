# Enhanced Dynamixel Error Handling Integration

This document describes the integration of enhanced error handling for Dynamixel motors into the LeRobot framework. The integration is designed to be **minimally invasive** and **backward compatible**.

## Overview

The enhanced error handling system provides:
- **Automatic detection** of Dynamixel motor errors (overloads, communication failures, etc.)
- **Intelligent recovery** from common error conditions like overloads
- **Non-intrusive monitoring** that doesn't affect normal operation
- **Clear logging** of all error conditions and recovery attempts

## Integration Points

The error handling is integrated at the following key points in the LeRobot framework:

### 1. Robot Configuration (`configs.py`)
```python
@dataclass
class ManipulatorRobotConfig(RobotConfig):
    # ... existing config ...
    
    # INTEGRATION POINT: Enhanced error monitoring configuration
    enable_error_monitoring: bool = True  # Enable/disable error monitoring
```

### 2. Robot Class (`manipulator.py`)
```python
class ManipulatorRobot:
    def __init__(self, config):
        # ... existing initialization ...
        
        # INTEGRATION POINT: Initialize error monitoring
        if DYNAMIXEL_ERROR_HANDLER_AVAILABLE and self.robot_type in ["aloha", "koch"]:
            self.error_monitor = DynamixelErrorMonitor(...)
        else:
            self.error_monitor = None
    
    def teleop_step(self, record_data=False):
        # INTEGRATION POINT: Check for errors before teleoperation
        if self.error_monitor is not None:
            self._check_and_handle_motor_errors()
        
        # ... existing teleoperation code ...
```

### 3. Control Loop (`control_utils.py`)
```python
def teleop_step(robot):
    # INTEGRATION POINT: Additional error handling hook
    # Main error handling is in robot.teleop_step()
    return robot.teleop_step(record_data=True)
```

### 4. Web Backend (`robot_service.py`)
```python
self.robot_cfg = AlohaRobotConfig(
    # ... existing config ...
    enable_error_monitoring=True,  # Enable error handling for web interface
)
```

## Configuration Options

### 1. Robot Configuration
Set `enable_error_monitoring=False` in your robot config to disable error monitoring:

```python
from lerobot.common.robot_devices.robots.configs import AlohaRobotConfig

config = AlohaRobotConfig(
    enable_error_monitoring=False  # Disable error monitoring
)
```

### 2. Environment Variable
Set the `DISABLE_ERROR_MONITORING=1` environment variable to disable globally:

```bash
export DISABLE_ERROR_MONITORING=1
python lerobot/scripts/control_robot.py --robot.type=aloha
```

### 3. Web Interface
Error monitoring is enabled by default in the web interface but can be disabled in the robot service configuration.

## How It Works

### Error Detection
- **Rate-limited checks**: Error checking occurs every 2 seconds (configurable)
- **Non-blocking**: Error checks don't slow down teleoperation
- **Comprehensive**: Monitors all hardware error status registers

### Error Recovery
- **Conservative approach**: Only attempts recovery for known safe conditions
- **Overload recovery**: Automatic recovery for motor overload errors
- **Manual fallback**: Other errors are logged for manual intervention

### Error Flow
1. **Detection**: Check `Hardware_Error_Status` register on each motor
2. **Classification**: Determine error type (overload, communication, etc.)
3. **Recovery**: For overload errors, attempt automatic recovery:
   - Disable torque
   - Reboot motor
   - Verify error cleared
   - Re-enable torque
4. **Logging**: All actions are clearly logged

## Error Codes

The system monitors the following Dynamixel hardware errors:

| Code | Description | Recovery |
|------|-------------|----------|
| 0x01 | Input Voltage Error | Log only |
| 0x02 | Motor Hall Sensor Error | Log only |
| 0x04 | Overheating Error | Log only |
| 0x08 | Motor Encoder Error | Log only |
| 0x10 | Electrical Shock Error | Log only |
| **0x20** | **Overload Error** | **Automatic recovery** |
| 0x40 | Instruction Error | Log only |
| 0x80 | Range Error | Log only |

## Usage Examples

### Basic Teleoperation with Error Handling
```bash
# Error handling is enabled by default
python lerobot/scripts/control_robot.py --robot.type=aloha
```

### Disable Error Handling for Debugging
```bash
# Option 1: Environment variable
export DISABLE_ERROR_MONITORING=1
python lerobot/scripts/control_robot.py --robot.type=aloha

# Option 2: Config override (if supported)
python lerobot/scripts/control_robot.py --robot.type=aloha --robot.enable_error_monitoring=false
```

### Web Interface
Error handling is automatically enabled in the web interface. Check the browser console and server logs for error handling messages.

## Testing

Run the integration test to verify error handling is working:

```bash
python test_error_handler_integration.py
```

This will check:
- ✓ Error handler module availability
- ✓ Robot config integration
- ✓ Robot class integration
- ✓ Control utils integration
- ✓ Error handler functionality

## Logging

Error handling produces clear log messages:

### Normal Operation
```
INFO: Dynamixel error monitoring enabled for aloha
```

### Error Detection
```
WARNING: Motor errors detected: {'follower_left': {'shoulder': 32}}
WARNING: Motor follower_left.shoulder has error: Overload Error
```

### Recovery
```
INFO: Overload detected on follower_left.shoulder, attempting recovery...
INFO: Successfully recovered follower_left.shoulder
```

### Recovery Failure
```
WARNING: Failed to recover follower_left.shoulder
```

## Safety Considerations

### Conservative Design
- **Non-intrusive**: Error monitoring doesn't interfere with normal operation
- **Fail-safe**: If error handling fails, normal operation continues
- **Rate-limited**: Error checks are limited to avoid performance impact

### What Gets Recovered
- **Overload errors**: Automatically recovered (safe for most cases)
- **Other errors**: Logged only (may require manual intervention)

### What Doesn't Change
- **Normal teleoperation**: Same responsiveness and behavior
- **Existing APIs**: All existing functions work exactly the same
- **Performance**: Minimal impact (rate-limited checks)

## Troubleshooting

### Error Handling Not Working
1. Check if error handler module is available:
   ```python
   from lerobot.common.robot_devices.motors.dynamixel_error_handler import DynamixelErrorMonitor
   ```

2. Check configuration:
   ```python
   print(robot.config.enable_error_monitoring)  # Should be True
   print(robot.error_monitor)  # Should not be None
   ```

3. Check environment variable:
   ```bash
   echo $DISABLE_ERROR_MONITORING  # Should be empty or 0
   ```

### Too Many Error Messages
Reduce error checking frequency by modifying `check_interval` in the error monitor:
```python
robot.error_monitor.check_interval = 5.0  # Check every 5 seconds instead of 2
```

### Disable for Specific Motors
The error monitoring checks all motors by default. To exclude specific motors, modify the `_check_and_handle_motor_errors` method in your robot class.

## Development Notes

### Adding New Robot Types
To enable error handling for new Dynamixel-based robots, add the robot type to the check in `manipulator.py`:

```python
if DYNAMIXEL_ERROR_HANDLER_AVAILABLE and self.robot_type in ["koch", "koch_bimanual", "aloha", "your_robot"]:
```

### Extending Error Recovery
To add recovery for new error types, modify the `attempt_motor_recovery` method in `dynamixel_error_handler.py`.

### Integration with Other Frameworks
The error handler is designed to be modular. The `DynamixelErrorMonitor` class can be used independently of the LeRobot framework integration.

## Summary

The enhanced error handling system provides robust error monitoring and recovery for Dynamixel motors while maintaining full backward compatibility with existing LeRobot code. It's designed to be:

- **Safe**: Conservative recovery only for known safe conditions
- **Non-intrusive**: Doesn't change existing behavior or performance
- **Configurable**: Can be easily enabled/disabled as needed
- **Well-logged**: All actions are clearly documented in logs

The integration points are clearly marked with comments and can be easily located, modified, or removed if needed.
