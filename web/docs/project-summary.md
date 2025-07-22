# LeLab - Simple Robotics Interface

## 🚀 Project Overview

LeLab is a streamlined web-based interface designed to simplify robotics operations, specifically built as the frontend for the [LeLab Hugging Face Space](https://huggingface.co/spaces/jurmy24/leLab). The project serves as an intuitive gateway to the LeRobot library, making complex robotics tasks accessible through a clean, modern interface.

## 🎯 Core Purpose

**Mission**: Provide a simple, user-friendly interface for robot arm control and dataset management without the complexity of traditional robotics frameworks.

**Target Users**: Researchers, developers, and robotics enthusiasts who need quick access to robot control and data collection capabilities.

## 🛠️ Key Features

### Robot Control
- **Teleoperation**: Real-time robot arm control with leader-follower configuration
- **Direct Control**: Mouse-based robot arm manipulation
- **URDF Visualization**: Interactive 3D robot model viewing and animation
- **Port Management**: Automatic detection and configuration of robot connections

### Data Management
- **Dataset Recording**: Capture robot movements and sensor data for training
- **Dataset Replay**: Analyze and review recorded episodes
- **Training Pipeline**: Model training capabilities (in development)

### User Experience
- **Clean Interface**: Minimalist design with dark theme
- **Auto-Configuration**: Smart defaults and automatic port detection
- **Real-time Feedback**: Live sensor and motor data visualization
- **3D Visualization**: Interactive robot models with Three.js integration

## 🏗️ Technical Architecture

### Frontend Stack
- **React + TypeScript**: Modern, type-safe component architecture
- **Vite**: Fast development and optimized builds
- **Three.js**: 3D graphics and robot visualization
- **Tailwind CSS**: Utility-first styling for consistent design

### Key Components
```
├── Robot Visualization (URDF Viewer)
├── Control Interfaces (Teleoperation, Direct Control)
├── Data Management (Recording, Replay)
└── Configuration (Port Detection, Calibration)
```

### Integration
- **Backend**: Connects to FastAPI server wrapping LeRobot library
- **Deployment**: Hosted on Hugging Face Spaces with Docker
- **Hardware**: Supports SO-ARM100/101 robotic arms

## 🎨 Design Philosophy

### Simplicity First
- **Minimal Learning Curve**: Intuitive controls that don't require robotics expertise
- **Clear Visual Hierarchy**: Important actions are prominently displayed
- **Progressive Disclosure**: Advanced features are accessible but not overwhelming

### Modern Aesthetics
- **Dark Theme**: Reduces eye strain during extended use
- **Consistent Spacing**: Clean layouts with proper visual breathing room
- **Color-Coded Actions**: Different operation types have distinct color schemes
- **Responsive Design**: Works across different screen sizes

### User-Centric Features
- **Auto-Save**: Settings and configurations persist automatically
- **Smart Defaults**: Sensible initial configurations reduce setup time
- **Real-time Updates**: Immediate feedback for all operations
- **Error Prevention**: Clear validation and helpful error messages

## 🔧 Supported Robot Models

### Currently Available
- **SO-ARM100**: Full teleoperation and control support
- **SO-ARM101**: Enhanced URDF support with ROS2 integration

### In Development
- **LeKiwi**: Future robot model support planned

## 🚦 Getting Started

The interface is designed for immediate use with minimal setup:

1. **Select Robot Model**: Choose your hardware from the main interface
2. **Configure Connections**: Use auto-detection for robot ports
3. **Choose Operation**: Pick from teleoperation, recording, or visualization
4. **Start Working**: Begin controlling or collecting data immediately

## 📈 Project Status

- ✅ **Production Ready**: Core teleoperation and visualization
- 🚧 **In Development**: Training pipeline and dataset replay
- 📋 **Planned**: Additional robot models and advanced features

## 🔗 Related Resources

- **Backend Repository**: [leLab FastAPI Server](https://github.com/nicolas-rabault/leLab)
- **Live Demo**: [LeLab on Hugging Face](https://huggingface.co/spaces/jurmy24/leLab)
- **Robot Hardware**: SO-ARM series robotic arms

---

*LeLab represents a new approach to robotics interfaces - prioritizing ease of use without sacrificing functionality. The project demonstrates that complex robotics operations can be made accessible through thoughtful design and modern web technologies.*