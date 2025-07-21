#!/usr/bin/env python3
"""
Desktop Shortcut Creation for LeRobot Web GUI
==============================================

Creates cross-platform desktop shortcuts for easy GUI access.
Supports Windows (.lnk), macOS (.app), and Linux (.desktop).
"""

import os
import sys
import platform
import subprocess
from pathlib import Path
from typing import Optional


class Colors:
    """ANSI color codes for terminal output"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'


def get_desktop_path() -> Path:
    """Get the user's desktop directory"""
    system = platform.system()
    
    if system == "Windows":
        desktop = Path.home() / "Desktop"
        if not desktop.exists():
            desktop = Path.home() / "OneDrive" / "Desktop"  # OneDrive desktop
        return desktop
    elif system == "Darwin":  # macOS
        return Path.home() / "Desktop"
    else:  # Linux
        desktop = Path.home() / "Desktop"
        if not desktop.exists():
            desktop = Path.home()  # Fallback to home
        return desktop


def create_windows_shortcut(force: bool = False) -> bool:
    """Create Windows .bat launcher and shortcut"""
    try:
        desktop = get_desktop_path()
        web_dir = Path(__file__).parent.parent
        
        # Create batch launcher
        launcher_content = f'''@echo off
REM LeRobot Web GUI Launcher
title LeRobot Web GUI
echo Starting LeRobot Web GUI...

REM Navigate to web directory
cd /d "{web_dir}"

REM Check if conda is available and lerobot environment exists
where conda >nul 2>nul
if %ERRORLEVEL% == 0 (
    conda info --envs | find "lerobot" >nul 2>nul
    if %ERRORLEVEL% == 0 (
        echo Activating conda lerobot environment...
        call conda activate lerobot
    ) else (
        echo Conda lerobot environment not found, using current Python...
    )
) else (
    echo Conda not found, using current Python...
)

REM Start LeRobot GUI
echo Starting LeRobot Web GUI...
python -m lerobot.web.cli gui

REM Keep window open if there's an error
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Error occurred. Press any key to close...
    pause >nul
)
'''
        
        launcher_path = desktop / "LeRobot_GUI_Launcher.bat"
        
        # Check if shortcut already exists
        if launcher_path.exists() and not force:
            print(f"{Colors.YELLOW}⚠️ Launcher already exists: {launcher_path}{Colors.RESET}")
            print(f"{Colors.CYAN}💡 Use --force to recreate{Colors.RESET}")
            return False
        
        # Write launcher
        with open(launcher_path, 'w') as f:
            f.write(launcher_content)
        
        print(f"{Colors.GREEN}✅ Windows launcher created: {launcher_path}{Colors.RESET}")
        
        # Try to create a proper .lnk shortcut (requires pywin32)
        try:
            import win32com.client
            
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut_path = desktop / "LeRobot GUI.lnk"
            
            if shortcut_path.exists() and not force:
                print(f"{Colors.YELLOW}⚠️ Shortcut already exists: {shortcut_path}{Colors.RESET}")
                return True
            
            shortcut = shell.CreateShortCut(str(shortcut_path))
            shortcut.Targetpath = str(launcher_path)
            shortcut.WorkingDirectory = str(web_dir)
            shortcut.Description = "LeRobot Web GUI - Modern interface for robot control"
            shortcut.IconLocation = str(launcher_path) + ",0"
            shortcut.save()
            
            print(f"{Colors.GREEN}✅ Windows shortcut created: {shortcut_path}{Colors.RESET}")
            
        except ImportError:
            print(f"{Colors.YELLOW}⚠️ pywin32 not available, using .bat launcher only{Colors.RESET}")
            print(f"{Colors.CYAN}💡 Install pywin32 for proper .lnk shortcuts: pip install pywin32{Colors.RESET}")
        
        return True
        
    except Exception as e:
        print(f"{Colors.RED}❌ Error creating Windows shortcut: {e}{Colors.RESET}")
        return False


def create_macos_app(force: bool = False) -> bool:
    """Create macOS .app bundle"""
    try:
        desktop = get_desktop_path()
        web_dir = Path(__file__).parent.parent
        app_path = desktop / "LeRobot GUI.app"
        
        if app_path.exists() and not force:
            print(f"{Colors.YELLOW}⚠️ App already exists: {app_path}{Colors.RESET}")
            print(f"{Colors.CYAN}💡 Use --force to recreate{Colors.RESET}")
            return False
        
        # Create app bundle structure
        contents_dir = app_path / "Contents"
        macos_dir = contents_dir / "MacOS"
        resources_dir = contents_dir / "Resources"
        
        contents_dir.mkdir(parents=True, exist_ok=True)
        macos_dir.mkdir(exist_ok=True)
        resources_dir.mkdir(exist_ok=True)
        
        # Create Info.plist
        plist_content = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>lerobot_gui</string>
    <key>CFBundleIdentifier</key>
    <string>com.lerobot.gui</string>
    <key>CFBundleName</key>
    <string>LeRobot GUI</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.9</string>
</dict>
</plist>'''
        
        with open(contents_dir / "Info.plist", 'w') as f:
            f.write(plist_content)
        
        # Create executable script
        script_content = f'''#!/bin/bash
# LeRobot GUI Launcher for macOS

cd "{web_dir}"

# Check if conda is available and activate lerobot environment
if command -v conda >/dev/null 2>&1; then
    if conda info --envs | grep -q "lerobot"; then
        echo "Activating conda lerobot environment..."
        source "$(conda info --base)/etc/profile.d/conda.sh"
        conda activate lerobot
    else
        echo "Conda lerobot environment not found, using current Python..."
    fi
else
    echo "Conda not found, using current Python..."
fi

# Start LeRobot GUI
echo "Starting LeRobot Web GUI..."
python -m lerobot.web.cli gui
'''
        
        script_path = macos_dir / "lerobot_gui"
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        # Make executable
        os.chmod(script_path, 0o755)
        
        print(f"{Colors.GREEN}✅ macOS app created: {app_path}{Colors.RESET}")
        return True
        
    except Exception as e:
        print(f"{Colors.RED}❌ Error creating macOS app: {e}{Colors.RESET}")
        return False


def create_linux_desktop(force: bool = False) -> bool:
    """Create Linux .desktop file"""
    try:
        desktop = get_desktop_path()
        web_dir = Path(__file__).parent.parent
        desktop_file = desktop / "lerobot-gui.desktop"
        
        if desktop_file.exists() and not force:
            print(f"{Colors.YELLOW}⚠️ Desktop file already exists: {desktop_file}{Colors.RESET}")
            print(f"{Colors.CYAN}💡 Use --force to recreate{Colors.RESET}")
            return False
        
        # Get Python executable path
        python_path = sys.executable
        
        desktop_content = f'''[Desktop Entry]
Version=1.0
Type=Application
Name=LeRobot GUI
Comment=Modern web interface for robot control and monitoring
Exec={python_path} -m lerobot.web.cli gui
Path={web_dir}
Icon=applications-science
Terminal=true
Categories=Science;Development;
StartupNotify=true
'''
        
        with open(desktop_file, 'w') as f:
            f.write(desktop_content)
        
        # Make executable
        os.chmod(desktop_file, 0o755)
        
        print(f"{Colors.GREEN}✅ Linux desktop file created: {desktop_file}{Colors.RESET}")
        
        # Try to add to applications menu
        try:
            applications_dir = Path.home() / ".local" / "share" / "applications"
            applications_dir.mkdir(parents=True, exist_ok=True)
            
            app_desktop_file = applications_dir / "lerobot-gui.desktop"
            if not app_desktop_file.exists() or force:
                with open(app_desktop_file, 'w') as f:
                    f.write(desktop_content)
                print(f"{Colors.GREEN}✅ Added to applications menu: {app_desktop_file}{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.YELLOW}⚠️ Could not add to applications menu: {e}{Colors.RESET}")
        
        return True
        
    except Exception as e:
        print(f"{Colors.RED}❌ Error creating Linux desktop file: {e}{Colors.RESET}")
        return False


def create_desktop_shortcut(force: bool = False) -> bool:
    """Create platform-appropriate desktop shortcut"""
    system = platform.system()
    
    print(f"{Colors.BOLD}🖥️ Creating desktop shortcut for {system}{Colors.RESET}")
    
    if system == "Windows":
        return create_windows_shortcut(force)
    elif system == "Darwin":
        return create_macos_app(force)
    else:  # Linux and others
        return create_linux_desktop(force)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Create LeRobot GUI desktop shortcut")
    parser.add_argument("--force", action="store_true", help="Force recreate existing shortcut")
    args = parser.parse_args()
    
    success = create_desktop_shortcut(force=args.force)
    sys.exit(0 if success else 1)
