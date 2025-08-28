"""
Dataset management module for LeRobot web interface.
Provides endpoints for browsing and visualizing local datasets.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel


router = APIRouter()


class DatasetInfo(BaseModel):
    """Dataset information model"""
    id: str
    name: str
    path: str
    episodes: int
    size: str
    created: str


class VisualizationRequest(BaseModel):
    """Request model for dataset visualization"""
    repo_id: str
    root_path: str


class DirectoryBrowseRequest(BaseModel):
    """Request model for directory browsing"""
    path: str


@router.get("/browse", response_model=List[DatasetInfo])
async def browse_local_datasets():
    """
    Browse local datasets in common data directories.
    Returns a list of discovered dataset directories.
    """
    datasets = []
    
    # Common dataset locations to check
    search_paths = [
        Path.home() / "data",
        Path.home() / "datasets", 
        Path("/data"),
        Path("/datasets"),
        Path(os.getcwd()) / "data",
        Path(os.getcwd()) / "datasets"
    ]
    
    for search_path in search_paths:
        if search_path.exists() and search_path.is_dir():
            try:
                for item in search_path.iterdir():
                    if item.is_dir():
                        # Check if it looks like a dataset directory
                        # (contains episode files or has dataset-like structure)
                        episode_files = list(item.glob("episode_*.parquet"))
                        if episode_files or (item / "data").exists():
                            datasets.append(DatasetInfo(
                                id=f"local_{item.name}",
                                name=item.name,
                                path=str(item),
                                episodes=len(episode_files),
                                size=_get_directory_size(item),
                                created=_get_creation_time(item)
                            ))
            except PermissionError:
                # Skip directories we can't access
                continue
    
    return datasets


@router.get("/info/{dataset_id}")
async def get_dataset_info(dataset_id: str):
    """
    Get detailed information about a specific dataset.
    """
    # This would typically query a database or filesystem
    # For now, return basic info
    return {
        "id": dataset_id,
        "message": f"Dataset info for {dataset_id}",
        "available": True
    }


@router.post("/visualize")
async def visualize_dataset(request: VisualizationRequest, background_tasks: BackgroundTasks):
    """
    Launch dataset HTML visualization.
    """
    try:
        # Validate paths
        root_path = Path(request.root_path)
        if not root_path.exists():
            raise HTTPException(status_code=400, detail=f"Root path does not exist: {request.root_path}")
        
        # Find the HTML visualize_dataset script
        script_path = Path(__file__).parent.parent.parent.parent / "lerobot" / "scripts" / "visualize_dataset_html.py"
        
        if not script_path.exists():
            raise HTTPException(status_code=500, detail="HTML visualization script not found")
        
        # Prepare command for HTML visualization (no episodes parameter - shows all episodes)
        cmd = [
            sys.executable,
            str(script_path),
            "--root", request.root_path,
            "--repo-id", request.repo_id,
            "--serve", "1",
            "--host", "127.0.0.1",
            "--port", "9090"
        ]
        
        # Launch visualization in background
        background_tasks.add_task(_run_visualization_command, cmd)
        
        return {
            "status": "launched",
            "message": f"HTML visualization started for {request.repo_id}",
            "command": " ".join(cmd),
            "web_url": "http://localhost:9090"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to launch visualization: {str(e)}")




@router.post("/browse-directory")
async def browse_directory(request: DirectoryBrowseRequest):
    """
    Browse directory contents for folder selection.
    Returns a list of subdirectories in the specified path.
    """
    try:
        raw_path = request.path.strip() if request.path else ''
        # Support home expansion using ~ similar to shell behavior
        if raw_path in ('', '~', '~/'):
            path = Path.home()
        elif raw_path.startswith('~/'):
            path = Path.home() / raw_path[2:]
        else:
            path = Path(raw_path)
        
        # Validate path exists and is accessible
        if not path.exists():
            raise HTTPException(status_code=400, detail=f"Path does not exist: {request.path}")
        
        if not path.is_dir():
            raise HTTPException(status_code=400, detail=f"Path is not a directory: {request.path}")
        
        folders = []
        
        try:
            # List only directories
            for item in path.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    try:
                        # Get basic folder info
                        stat_info = item.stat()
                        folders.append({
                            "name": item.name,
                            "path": str(item),
                            "permissions": oct(stat_info.st_mode)[-3:] if hasattr(stat_info, 'st_mode') else None
                        })
                    except (OSError, PermissionError):
                        # Skip folders we can't access
                        continue
                        
        except PermissionError:
            raise HTTPException(status_code=403, detail=f"Permission denied accessing: {request.path}")
        
        # Sort folders alphabetically
        folders.sort(key=lambda x: x['name'].lower())
        
        return {
            "path": str(path),
            "folders": folders,
            "total": len(folders)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to browse directory: {str(e)}")


@router.get("/count")
async def get_dataset_count():
    """
    Get count of local datasets for dashboard.
    """
    try:
        datasets = await browse_local_datasets()
        return {
            "count": len(datasets),
            "total": len(datasets)
        }
    except Exception as e:
        return {
            "count": 0,
            "total": 0,
            "error": str(e)
        }


def _get_directory_size(path: Path) -> str:
    """Get human-readable directory size"""
    try:
        total_size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
        # Convert to human readable format
        for unit in ['B', 'KB', 'MB', 'GB']:
            if total_size < 1024:
                return f"{total_size:.1f} {unit}"
            total_size /= 1024
        return f"{total_size:.1f} TB"
    except (OSError, PermissionError):
        return "Unknown"


def _get_creation_time(path: Path) -> str:
    """Get directory creation time"""
    try:
        import datetime
        timestamp = path.stat().st_ctime
        return datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
    except (OSError, PermissionError):
        return "Unknown"


async def _run_visualization_command(cmd: List[str]):
    """
    Run visualization command in background.
    """
    try:
        # Run the command
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Don't wait for completion to allow background execution
        print(f"Started visualization process with PID: {process.pid}")
        print(f"Command: {' '.join(cmd)}")
        
        # Track the process
        import datetime
        _visualization_processes[process.pid] = {
            "process": process,
            "command": " ".join(cmd),
            "started_at": datetime.datetime.now().isoformat(),
            "web_url": "http://localhost:9090",
            "ws_url": "ws://localhost:9087"
        }
        
    except Exception as e:
        print(f"Error running visualization command: {e}")


# Global variable to track visualization processes
_visualization_processes = {}


@router.get("/visualization/status")
async def get_visualization_status():
    """
    Get status of running visualization processes.
    """
    active_processes = []
    
    # Clean up finished processes
    finished_pids = []
    for pid, process_info in _visualization_processes.items():
        if process_info["process"].poll() is not None:  # Process has finished
            finished_pids.append(pid)
    
    for pid in finished_pids:
        del _visualization_processes[pid]
    
    # Return active processes
    for pid, process_info in _visualization_processes.items():
        active_processes.append({
            "pid": pid,
            "command": process_info["command"],
            "started_at": process_info["started_at"],
            "web_url": process_info.get("web_url"),
            "ws_url": process_info.get("ws_url")
        })
    
    return {
        "active_processes": active_processes,
        "total": len(active_processes)
    }


@router.post("/visualization/stop")
async def stop_visualization():
    """
    Stop all running visualization processes.
    """
    stopped_count = 0
    
    for pid, process_info in _visualization_processes.items():
        try:
            process = process_info["process"]
            if process.poll() is None:  # Still running
                process.terminate()
                stopped_count += 1
        except Exception as e:
            print(f"Error stopping process {pid}: {e}")
    
    # Clear the tracking dictionary
    _visualization_processes.clear()
    
    return {
        "status": "stopped",
        "message": f"Stopped {stopped_count} visualization processes"
    }
