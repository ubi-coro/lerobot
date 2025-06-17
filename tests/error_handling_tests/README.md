# LeRobot Error Handling Tests and Documentation

This directory contains comprehensive tests and documentation for the Dynamixel error handling system in LeRobot.

## Test Files

1. **test_direct_error_handler.py**
   - Direct functional tests of the error handler
   - Simulates error conditions and tests recovery procedures
   - Usage: `python -m tests.error_handling_tests.test_direct_error_handler`

2. **test_error_handler_integration.py**
   - Tests integration of error handling with the LeRobot framework
   - Verifies config options, methods, and hooks are properly connected
   - Usage: `python -m tests.error_handling_tests.test_error_handler_integration`

3. **test_error_handler_real_robot.py**
   - Tests for running on actual robot hardware
   - Monitors for errors during real-world operation
   - Usage: `python -m tests.error_handling_tests.test_error_handler_real_robot`

4. **test_error_handler_simulation.py**
   - Simulates errors during teleoperation
   - Tests recovery during operation
   - Usage: `python -m tests.error_handling_tests.test_error_handler_simulation`

## Documentation Files

1. **DYNAMIXEL_ERROR_HANDLING.md**
   - Technical documentation of the error handling system
   - Integration points and implementation details

2. **ERROR_HANDLING_USER_GUIDE.md**
   - User-focused guide to the error handling features
   - How to enable/disable and configure error handling

3. **ERROR_HANDLING_TEST_RESULTS.md**
   - Summary of test results and verification status

## Standard Unit Tests

In addition to these specialized test files, standard pytest unit tests are available at:
- `tests/motors/test_dynamixel_error_handler.py` - pytest-compatible unit tests for the error handler

## Running Tests

You can run all the error handling tests using the following command:

```bash
cd /home/jannick/PycharmProjects/lerobot
python -m pytest tests/motors/test_dynamixel_error_handler.py
python -m tests.error_handling_tests.test_direct_error_handler
python -m tests.error_handling_tests.test_error_handler_integration
```

For real hardware testing:
```bash
python -m tests.error_handling_tests.test_error_handler_real_robot
```
