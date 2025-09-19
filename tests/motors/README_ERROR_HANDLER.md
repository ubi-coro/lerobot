# Dynamixel Error Handler Testing

This directory contains organized tests for the Dynamixel error handling functionality.

## Test Files

### Standard Unit Tests (in tests/motors/)

- **test_dynamixel_error_handler.py**: Unit tests for the DynamixelErrorMonitor class using pytest.
  - Tests error detection, recovery procedures, rate limiting, and integration with robot structure
  - Can be run with: `pytest tests/motors/test_dynamixel_error_handler.py`

### Additional Test Scripts (in tests/error_handling_tests/)

More comprehensive test scripts with different purposes are located in the dedicated folder:

1. **test_error_handler_integration.py**
   - Purpose: Tests proper integration of error handling into the LeRobot framework
   - Checks: Configuration options, class initialization, method availability
   - Usage: `python -m tests.error_handling_tests.test_error_handler_integration`

2. **test_direct_error_handler.py**
   - Purpose: Direct functional test of error handling without pytest framework
   - Tests: Core functionality of error detection and recovery
   - Usage: `python -m tests.error_handling_tests.test_direct_error_handler`

3. **test_error_handler_real_robot.py**
   - Purpose: Test error handling with a real robot in actual operation
   - Tests: Integration with teleoperation and real hardware
   - Usage: `python -m tests.error_handling_tests.test_error_handler_real_robot`

4. **test_error_handler_simulation.py**
   - Purpose: Simulate errors during teleoperation 
   - Tests: Error injection during operation
   - Usage: `python -m tests.error_handling_tests.test_error_handler_simulation`

## Documentation

Documentation files are also available in the tests/error_handling_tests directory:

- **DYNAMIXEL_ERROR_HANDLING.md**: Technical documentation of the error handling system
- **ERROR_HANDLING_USER_GUIDE.md**: User guide for working with the error handling features
- **ERROR_HANDLING_TEST_RESULTS.md**: Summary of test results and verification status

## Running Tests

For standard unit tests:
```bash
cd /home/jannick/PycharmProjects/lerobot
pytest tests/motors/test_dynamixel_error_handler.py
```

For integration testing:
```bash
python -m tests.error_handling_tests.test_error_handler_integration
```

For real hardware testing:
```bash
python -m tests.error_handling_tests.test_error_handler_real_robot
```

## Full Documentation

For full documentation and all test files, see:
```bash
cd /home/jannick/PycharmProjects/lerobot/tests/error_handling_tests
```
