# LeLab Project Analysis & Technical Summary

## 🎯 Project Overview

**LeLab** is a modern web-based interface that bridges the gap between the [LeRobot framework](https://github.com/huggingface/lerobot) and user-friendly robotics control. It provides a complete solution for robot teleoperation, data recording, and ML model training through an intuitive web dashboard.

### Key Value Proposition
- **Web-first approach**: Modern React frontend with real-time WebSocket communication
- **Direct LeRobot integration**: Uses LeRobot as a dependency, not a separate service
- **Complete robotics workflow**: From teleoperation → data recording → training → replay
- **Plug-and-play architecture**: Automated frontend management and browser launching

---

## 🏗️ System Architecture

### High-Level Architecture
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │    │   FastAPI        │    │   LeRobot       │
│   (React/TS)    │◄──►│   Backend        │◄──►│   Framework     │
│   Port 8080     │    │   Port 8000      │    │                 │
│                 │    │                  │    │                 │
│   • Dashboard   │    │   • REST APIs    │    │   • Robot       │
│   • Controls    │    │   • WebSockets   │    │     Control     │
│   • Monitoring  │    │   • Recording    │    │   • Sensors     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Technology Stack

#### Backend (Python)
- **FastAPI**: Modern async web framework
- **WebSockets**: Real-time bidirectional communication
- **LeRobot**: Direct integration as pip dependency
- **Uvicorn**: ASGI server for production
- **Threading**: Concurrent execution for robot operations

#### Frontend (React - Auto-managed)
- **Repository**: [leLab-space](https://github.com/jurmy24/leLab-space.git)
- **Auto-cloning**: Automatically cloned to parent directory
- **Vite**: Development server with hot reload
- **TypeScript**: Type-safe development
- **Tailwind CSS**: Modern UI styling

#### Integration Strategy
- **Dependency model**: `lerobot @ git+https://github.com/huggingface/lerobot.git`
- **Direct imports**: LeRobot components imported directly into Python modules
- **Event-driven**: Web events replace keyboard controls in LeRobot CLI

---

## 🚀 Deployment & Launch System

### Command-Line Interface
```bash
# Backend only
lelab

# Full-stack (most common)
lelab-fullstack  

# Frontend development only
lelab-frontend
```

### Automated Frontend Management
- **Auto-detection**: Checks for existing frontend in `../leLab-space/`
- **Auto-cloning**: Clones from GitHub if not found
- **Dependency management**: Runs `npm install` automatically
- **Browser launching**: Opens `http://localhost:8080` automatically
- **Process management**: Handles both backend and frontend lifecycle

### Development Workflow
```python
# scripts/fullstack.py - Key implementation
def start_frontend_detached(frontend_path):
    frontend_process = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=frontend_path,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,  # Detached process
    )

def start_backend_detached():
    backend_process = subprocess.Popen([
        sys.executable, "-m", "uvicorn",
        "app.main:app", "--host", "0.0.0.0", 
        "--port", "8000", "--reload"
    ])
```

---

## 🎮 Core Features & Implementation

### 1. Robot Teleoperation (`app/teleoperating.py`)

#### Key Components
```python
from lerobot.common.teleoperators.so101_leader import SO101LeaderConfig, SO101Leader
from lerobot.common.robots.so101_follower import SO101FollowerConfig, SO101Follower

class TeleoperateRequest(BaseModel):
    leader_port: str      # COM port for leader device
    follower_port: str    # COM port for follower robot
    leader_config: str    # Calibration config file
    follower_config: str  # Calibration config file
```

#### Real-time Communication
- **WebSocket endpoint**: `/ws/joint-data`
- **Broadcast frequency**: 20 FPS (50ms intervals)
- **Joint data format**: URDF-compatible joint names
- **Connection management**: Auto-cleanup on disconnect

#### Implementation Pattern
```python
def teleoperation_worker():
    robot = SO101Follower(robot_config)
    teleop_device = SO101Leader(teleop_config)
    
    # Connect and calibrate
    robot.bus.connect()
    robot.bus.write_calibration(robot.calibration)
    
    # Main control loop
    while teleoperation_active:
        action = teleop_device.get_action()
        robot.send_action(action)
        
        # Broadcast joint positions via WebSocket
        joint_positions = get_joint_positions_from_robot(robot)
        websocket_manager.broadcast_joint_data_sync(joint_data)
```

### 2. Data Recording (`app/recording.py`)

#### Event-Driven Recording
- **Replaces keyboard controls**: Web buttons replace arrow keys and ESC
- **Phase tracking**: "preparing" → "recording" → "resetting" → "completed"
- **Episode management**: Skip, re-record, stop controls
- **Camera integration**: OpenCV camera configuration

#### Core Recording Flow
```python
class RecordingRequest(BaseModel):
    dataset_repo_id: str     # HuggingFace dataset ID
    single_task: str         # Task description
    num_episodes: int = 5    # Number of episodes to record
    episode_time_s: int = 30 # Episode duration
    reset_time_s: int = 10   # Reset time between episodes
    cameras: dict = {}       # Camera configurations
    
def record_with_web_events(cfg: RecordConfig, web_events: dict):
    # Mirrors original LeRobot record() function exactly
    # but uses web_events instead of keyboard input
    while saved_episodes < cfg.dataset.num_episodes:
        # RECORDING PHASE
        record_loop(robot=robot, events=web_events, 
                   dataset=dataset, ...)
        
        # Handle web controls
        if web_events["rerecord_episode"]:
            # Re-record without incrementing episode
            continue
        if web_events["exit_early"]:
            # Save and move to next episode
            dataset.save_episode()
```

#### Camera Resource Management
```python
# Critical: Wait for frontend camera streams to release
if request.cameras:
    logger.info("🔓 BACKEND: Waiting for camera resources...")
    time.sleep(2.0)  # Allow frontend to release cameras
```

### 3. Robot Calibration (`app/calibrating.py`)

#### Web-Guided Calibration Process
- **Step 1 - Homing**: Move robot to center position
- **Step 2 - Range Recording**: Move joints through full range
- **Auto-completion**: Saves calibration files automatically

#### Implementation Architecture
```python
class CalibrationManager:
    def start_calibration(self, request: CalibrationRequest):
        # Thread-based execution
        self.calibration_thread = threading.Thread(
            target=self._calibration_worker, args=(request,)
        )
        
    def _step_homing(self):
        # Disable torque for manual movement
        self.device.bus.disable_torque()
        # Wait for user to complete step via web interface
        while not self._step_complete.is_set():
            time.sleep(0.1)
            
    def _step_range_recording(self):
        # Real-time position tracking
        while not self._step_complete.is_set():
            positions = self.device.bus.sync_read("Present_Position")
            # Update min/max ranges
            for motor, pos in positions.items():
                self._mins[motor] = min(self._mins[motor], pos)
                self._maxes[motor] = max(self._maxes[motor], pos)
```

### 4. ML Training (`app/training.py`)

#### CLI Integration
- **Direct LeRobot CLI**: Spawns `lerobot train` as subprocess
- **Parameter mapping**: Web form → CLI arguments
- **Real-time monitoring**: Log parsing and status updates

```python
class TrainingRequest(BaseModel):
    dataset_repo_id: str
    policy_type: str = "act"  # act, diffusion, etc.
    steps: int = 10000
    batch_size: int = 8
    # ... extensive parameter support

def _build_training_command(self, request: TrainingRequest) -> list:
    cmd = ["python", "-m", "lerobot.train"]
    cmd.extend(["--dataset.repo_id", request.dataset_repo_id])
    cmd.extend(["--policy.type", request.policy_type])
    # ... builds complete CLI command
```

### 5. Model Replay (`app/replaying.py`)

#### Dataset Playback
- **Robot validation**: Checks motor connectivity before replay
- **Episode selection**: Choose specific episodes to replay
- **Multi-robot support**: SO-101 and SO-100 followers

```python
def run_replay_directly(request: ReplayRequest):
    # Create robot config dynamically
    if request.robot_type == "so101_follower":
        robot_config = SO101FollowerConfig(
            port=request.robot_port,
            id=follower_config_name,
        )
    
    # Validate robot before replay
    test_robot = make_robot_from_config(robot_config)
    test_robot.connect()
    test_robot.bus.read("Present_Position")  # Connectivity test
```

---

## 🔧 Configuration Management (`app/config.py`)

### Calibration File System
```python
# Standardized paths following LeRobot conventions
CALIBRATION_BASE_PATH_TELEOP = "~/.cache/huggingface/lerobot/calibration/teleoperators"
CALIBRATION_BASE_PATH_ROBOTS = "~/.cache/huggingface/lerobot/calibration/robots"

def setup_calibration_files(leader_config: str, follower_config: str):
    # Automatic file copying to correct LeRobot locations
    # Ensures calibration files are accessible to LeRobot
```

### Port Detection & Management
- **Cross-platform**: Windows COM ports, Linux/macOS /dev/tty*
- **Auto-detection**: Disconnect/reconnect detection method
- **Persistent storage**: Saves discovered ports for reuse

```python
def find_available_ports():
    if platform.system() == "Windows":
        ports = [port.device for port in list_ports.comports()]
    else:
        ports = [str(path) for path in Path("/dev").glob("tty*")]
```

---

## 🌐 API Architecture

### REST Endpoints

#### Teleoperation
```
POST /move-arm              - Start teleoperation
POST /stop-teleoperation    - Stop current session
GET  /teleoperation-status  - Get current status
GET  /joint-positions       - Get current joint states
```

#### Recording
```
POST /start-recording          - Begin dataset recording
POST /stop-recording           - End recording session
POST /recording-exit-early     - Skip to next episode
POST /recording-rerecord-episode - Re-record current episode
GET  /recording-status         - Get recording progress
```

#### Configuration
```
GET  /get-configs              - List available calibrations
GET  /available-ports          - List serial ports
POST /save-robot-port          - Save port configuration
GET  /calibration-configs/{type} - Get calibration files
```

#### Training & Replay
```
POST /start-training    - Start ML training
POST /start-replay      - Start model replay
GET  /training-logs     - Get training progress
GET  /replay-status     - Get replay status
```

### WebSocket Communication
```
WS /ws/joint-data - Real-time joint position updates
```

#### WebSocket Data Format
```json
{
  "type": "joint_update",
  "joints": {
    "Rotation": 0.123,
    "Pitch": -0.456,
    "Elbow": 1.234,
    "Wrist_Pitch": 0.789,
    "Wrist_Roll": -0.234,
    "Jaw": 0.567
  },
  "timestamp": 1703123456.789
}
```

---

## 🔄 State Management & Threading

### Global State Variables
```python
# Teleoperation state
teleoperation_active = False
current_robot = None
current_teleop = None

# Recording state  
recording_active = False
recording_events = {
    "exit_early": False,
    "stop_recording": False, 
    "rerecord_episode": False
}
current_episode = 1
saved_episodes = 0
current_phase = "preparing"
```

### Thread Management Patterns
- **ThreadPoolExecutor**: For long-running robot operations
- **Background processes**: Detached frontend/backend processes
- **Event-based coordination**: Threading.Event for step completion
- **Resource cleanup**: Automatic disconnect on thread completion

---

## 🔒 Robot Hardware Integration

### Supported Hardware (Currently)
- **SO-101 Leader**: Teleoperation controller
- **SO-101 Follower**: Robot arm
- **SO-100 Follower**: Alternative robot arm (replay only)

### Hardware Abstraction
```python
# Consistent interface across robot types
robot = SO101Follower(robot_config)
robot.bus.connect()
robot.bus.write_calibration(robot.calibration)
robot.configure()

# Action-observation loop
action = teleop_device.get_action()
robot.send_action(action)
observation = robot.get_observation()
```

### Calibration Management
- **Motor-level calibration**: Homing offsets, range limits
- **Persistent storage**: JSON files in LeRobot cache directory
- **Hot-loading**: Calibration applied without restart

---

## 🎨 User Experience Design

### Workflow Philosophy
1. **Guided processes**: Step-by-step calibration and recording
2. **Real-time feedback**: Live joint positions, recording status
3. **Error recovery**: Re-record episodes, resume recording
4. **Auto-management**: Frontend cloning, dependency installation

### Status Communication
- **Phase tracking**: Clear indication of current operation phase
- **Progress indicators**: Episode counters, time remaining
- **Error handling**: Graceful degradation with informative messages

---

## 📊 Key Technical Insights

### 1. Event-Driven Architecture
- **Replaces CLI keyboard input**: Web buttons trigger same events as keyboard
- **Maintains LeRobot compatibility**: Uses original record/teleop functions
- **Non-blocking operations**: Background threads for robot operations

### 2. Resource Management
- **Camera conflicts**: Explicit camera release timing
- **Port contention**: Retry logic for serial port access
- **Memory management**: Proper cleanup of robot connections

### 3. Development Experience
- **Hot reload**: Both frontend and backend support live reloading
- **Auto-setup**: No manual frontend management required
- **Cross-platform**: Windows PowerShell and Unix shell support

### 4. Scalability Considerations
- **Robot factory pattern**: Easy to add new robot types
- **Modular design**: Separate modules for each major feature
- **Configuration-driven**: Robot types defined in config files

---

## 🔧 Extension Points for Your Project

### 1. Multi-Robot Support
```python
# Current limitation - hardcoded to SO-101
from lerobot.common.robots.so101_follower import SO101Follower

# Extension opportunity - robot factory
class RobotFactory:
    SUPPORTED_ROBOTS = {
        "so101_follower": SO101Follower,
        "aloha": AlohaRobot,
        "your_robot": YourRobotClass,
    }
```

### 2. Frontend Architecture
- **Separate repository**: Frontend in different repo allows independent development
- **API-first design**: Clean separation between UI and robotics logic
- **Modern stack**: React + TypeScript + Vite for fast development

### 3. Configuration Management
- **Centralized config**: All calibration files in standard locations
- **Auto-detection**: Port and camera discovery
- **Persistent preferences**: Saved configurations between sessions

### 4. Real-time Communication
- **WebSocket pattern**: Bidirectional real-time updates
- **Broadcast system**: Multiple clients can connect simultaneously
- **Connection management**: Automatic cleanup and reconnection

---

## 🚨 Limitations & Considerations

### Current Robot Support
- **Limited to SO-101/SO-100**: Only specific robot models supported
- **Hardcoded configurations**: Robot types defined in code, not config

### Camera Management
- **Resource conflicts**: Frontend must release cameras before recording
- **Manual timing**: 2-second delays to ensure resource release

### Threading & State
- **Global state**: Some use of global variables for state management
- **Thread coordination**: Complex coordination between web events and robot threads

### Error Handling
- **Port contention**: Multiple retry mechanisms for serial port access
- **Resource cleanup**: Extensive finally blocks for proper cleanup

---

## 💡 Recommendations for Your Project

### 1. Architecture Decisions
- **Consider the repository split**: Separate frontend repo enables independent teams
- **Event-driven design**: Web events replacing CLI controls is elegant
- **Direct dependency approach**: Installing LeRobot as dependency vs. service approach

### 2. Development Workflow
- **Auto-management**: The automatic frontend cloning/setup is very user-friendly
- **Command patterns**: Multiple launch modes (backend-only, frontend-only, full-stack)
- **Hot reload**: Essential for rapid development

### 3. Technical Patterns
- **ThreadPoolExecutor**: Good pattern for robot operations
- **WebSocket broadcasting**: Efficient for real-time updates
- **Configuration file management**: Standardized paths and auto-copying

### 4. User Experience
- **Guided workflows**: Step-by-step processes reduce user errors
- **Real-time feedback**: Essential for robotics applications
- **Error recovery**: Re-record and resume capabilities are crucial

---

## 📚 Key Files to Study

### Core Application
- `app/main.py` - FastAPI app and endpoint definitions
- `app/teleoperating.py` - Real-time robot control implementation
- `app/recording.py` - Dataset recording with web event integration

### Configuration & Setup
- `app/config.py` - Configuration management and file handling
- `scripts/fullstack.py` - Multi-process launch and management
- `pyproject.toml` - Dependency management and CLI commands

### Feature Modules
- `app/calibrating.py` - Web-guided calibration process
- `app/training.py` - ML training integration
- `app/replaying.py` - Model replay functionality

This analysis should provide a comprehensive foundation for comparing with your project and identifying improvement opportunities. The LeLab approach offers particularly strong patterns for web-robotics integration, development workflow automation, and user experience design.
