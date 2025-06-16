Design and implement configurable teleoperation options for the LeRobot framework's ALOHA system, with the following specifications:

1. Configuration Structure:
- Create two tiers of settings:
  - Standard options for common use cases
  - Expert options for advanced customization

2. Default Configuration:
- Implement sensible defaults for:
  - Control frequency (200 Hz maximum)
  - Camera settings
  - Input device mappings
  - Safety limits

3. Standard Options:
- Control frequency adjustment (e.g., 30 Hz, 60 Hz, 200 Hz)
- Camera stream toggle
- Emergency stop configuration
- Basic movement speed controls

4. Expert Options:
- Fine-grained frequency control
- Custom input device mapping
- Advanced safety parameters
- Performance monitoring
- Debug logging levels

5. Implementation Requirements:
- Use configuration files for persistent settings
- Implement command-line argument support
- Maintain backward compatibility with existing scripts
- Add validation for all configuration parameters

6. Documentation:
- Document all configuration options
- Provide example configurations
- Include usage instructions for both standard and expert modes

Reference the existing implementation:
```bash
python lerobot/scripts/control_robot.py --robot.type=aloha --control.type=teleoperate
```

Follow the LeRobot framework's configuration standards and ensure all options are thoroughly tested.