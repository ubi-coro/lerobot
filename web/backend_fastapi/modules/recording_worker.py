"""GUI Recording Worker (Phase 1)
=================================

Implements an adapter-based wrapper around the existing LeRobot
`record()` orchestration without modifying upstream code.

Phase 1 goals:
 - Start/stop dataset recording from the GUI via Socket.IO
 - Minimal status emission (episodes, frames, fps, timing)
 - Support basic rerecord / skip / stop controls
 - Reuse already connected robot (teleoperation or robot_service) when possible

Deferred to later phases:
 - Policy/eval (interactive) runs
 - Intervention toggling
 - Fine‑grained per-frame latency metrics
 - Push-to-hub manual trigger beyond cfg.push_to_hub
 - Resume validation UI / advanced queue metrics

Design notes:
 - We duplicate a small portion of `record()` logic to inject a custom
   event adapter (thread-safe) instead of the keyboard listener.
 - A background asyncio task emits status every 0.5s.
 - Heavy recording loop runs in a dedicated thread (blocking).
 - Dataset frame counting is achieved by monkeypatching `dataset.add_frame`.
"""

from __future__ import annotations

import threading
import time
import logging
import asyncio
from dataclasses import asdict
from typing import Any, Dict, Optional

from lerobot.common.robot_devices.control_configs import RecordControlConfig
from lerobot.common.robot_devices.control_utils import (
    warmup_record,
    record_episode,
    reset_environment,
    stop_recording as core_stop_recording,
    sanity_check_dataset_name,
    sanity_check_dataset_robot_compatibility,
    ControlEvents,
)
from lerobot.common.datasets.lerobot_dataset import LeRobotDataset
from lerobot.common.utils.utils import has_method, log_say
from lerobot.scripts.control_robot import _init_rerun  # for display_data parity

logger = logging.getLogger(__name__)

try:  # Optional imports for robot reuse
    from .aloha_teleoperation import aloha_state  # type: ignore
except Exception:  # pragma: no cover - optional
    aloha_state = None

try:
    # Import the module, not the variable, to avoid stale references.
    from . import robot as robot_module  # type: ignore
except Exception:  # pragma: no cover
    robot_module = None

try:
    import shared  # global Socket.IO accessor
except Exception as e:  # pragma: no cover
    shared = None  # type: ignore
    logger.warning(f"Shared socket module not available: {e}")


class ApiEventAdapter(ControlEvents):
    """Thread-safe replacement for keyboard-driven ControlEvents.

    Flags used by upstream logic:
      exit_early, rerecord_episode, stop_recording, intervention (unused phase 1)
    """

    def __init__(self):
        super().__init__(
            {
                "exit_early": False,
                "rerecord_episode": False,
                "stop_recording": False,
                "intervention": False,
            }
        )
        self._lock = threading.Lock()

    def set_flag(self, key: str, value: bool = True):
        with self._lock:
            if key in self:
                self[key] = value

    def toggle(self, key: str):
        with self._lock:
            if key in self:
                self[key] = not self[key]

    def reset(self):  # override to keep thread safety
        with self._lock:
            self["exit_early"] = False
            self["rerecord_episode"] = False
            # do not reset stop_recording here
            self["intervention"] = False

    def update(self):  # upstream calls this each loop; nothing required
        return


class RecordingWorkerState:
    def __init__(self):
        self.active: bool = False
        self.thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.events: Optional[ApiEventAdapter] = None
        self.cfg: Optional[RecordControlConfig] = None
        self.dataset: Optional[LeRobotDataset] = None
        self.episode_index: int = 0
        self.total_frames: int = 0
        self.episode_frames: int = 0
        self.episode_start_t: float | None = None
        # Phase tracking (for countdown progress): one of "idle","warmup","recording","resetting","transition"
        self.phase: str = "idle"
        self.phase_start_t: float | None = None
        self.phase_total_s: float | None = None
        self.status_lock = threading.Lock()
        self.last_status: Dict[str, Any] = {}
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.display_data_session_started = False

    def snapshot(self) -> Dict[str, Any]:
        with self.status_lock:
            now = time.perf_counter()
            episode_elapsed = None
            if self.episode_start_t is not None:
                episode_elapsed = now - self.episode_start_t
            phase_elapsed = None
            if self.phase_start_t is not None:
                phase_elapsed = now - self.phase_start_t
            return {
                "active": self.active,
                "episode_index": self.episode_index,
                "total_episodes": getattr(self.cfg, "num_episodes", 0) or 0,
                "episode_frames": self.episode_frames,
                "total_frames": self.total_frames,
                "episode_elapsed_s": episode_elapsed,
                "episode_duration_s": getattr(self.cfg, "episode_time_s", 0) or 0,
                "repo_id": getattr(self.cfg, "repo_id", None),
                "single_task": getattr(self.cfg, "single_task", None),
                "fps_target": getattr(self.cfg, "fps", 0) or 0,
                # fps_current simple estimate: frames / elapsed
                "fps_current": (
                    (self.episode_frames / episode_elapsed) if episode_elapsed and episode_elapsed > 0 else None
                ),
                # UI hint: if a re-record has been requested for the current episode
                "rerecord_pending": bool(self.events["rerecord_episode"]) if self.events is not None else False,
                # Phase & countdown support for UI
                "phase": self.phase,
                "phase_elapsed_s": phase_elapsed or 0,
                "phase_total_s": self.phase_total_s or 0,
                # Keep legacy 'state' for compatibility but align with phase
                "state": self.phase if self.active or self.phase != "idle" else "idle",
            }

    def _event_flag(self, key: str) -> bool:
        try:
            if self.events is None:
                return False
            # ApiEventAdapter supports dict-like access
            return bool(self.events[key])
        except Exception:
            return False


recording_worker = RecordingWorkerState()


def _get_robot_instance():
    """Attempt to reuse an existing connected robot instance."""
    # Teleoperation robot reuse
    if aloha_state and aloha_state.get("robot") is not None:
        robot = aloha_state["robot"]
        try:
            if robot.is_connected:
                return robot, False
        except Exception:  # pragma: no cover
            pass
    # Robot service reuse (access dynamically from module to avoid stale import)
    if robot_module and getattr(robot_module, "robot_service", None) is not None:
        robot = getattr(robot_module, "robot_service").robot
        try:
            if robot and robot.is_connected:
                # Log basic diagnostics about cameras
                try:
                    cam_count = len(getattr(robot, "cameras", {}) or {})
                    logger.info("Robot instance ready (type=%s, cameras=%d)", getattr(robot, "robot_type", "?"), cam_count)
                except Exception:
                    pass
                return robot, False
        except Exception:  # pragma: no cover
            pass
    # Otherwise fail (no autonomous robot creation here)
    raise RuntimeError(
        "No connected robot available. Connect via teleoperation or robot endpoint before starting recording."
    )


def start_recording_via_api(config: Dict[str, Any]):
    if recording_worker.active:
        raise RuntimeError("Recording already active")

    # Minimal required fields validation
    required = ["repo_id", "single_task", "fps", "episode_time_s", "num_episodes"]
    missing = [k for k in required if k not in config]
    if missing:
        raise ValueError(f"Missing required config fields: {missing}")

    # Sanitize numeric fields to avoid None-related crashes (e.g., coming from JSON null)
    def _num(x, default=None):
        return default if x is None else x

    def _pos_int(x, default=None):
        try:
            return int(x)
        except Exception:
            return default

    def _pos_float(x, default=None):
        try:
            # Accept ints or strings that represent numbers
            return float(x)
        except Exception:
            return default

    warmup_time_s = _pos_float(config.get("warmup_time_s"), 10.0)
    episode_time_s = _pos_float(config.get("episode_time_s"), 30.0)
    reset_time_s = _pos_float(config.get("reset_time_s"), 10.0)
    fps_val = config.get("fps")
    if fps_val is None:
        raise ValueError("fps must be provided and non-null")
    fps_val = _pos_int(fps_val, None)
    if fps_val is None or fps_val <= 0:
        raise ValueError(f"Invalid fps value: {config.get('fps')} (must be a positive integer)")

    num_img_writer_proc = _pos_int(config.get("num_image_writer_processes", 0), 0)
    num_img_writer_threads_per_cam = _pos_int(config.get("num_image_writer_threads_per_camera", 4), 4)

    # Sanitize num_episodes
    num_episodes_val = config.get("num_episodes", 1)
    if num_episodes_val is None:
        num_episodes_val = 1
    else:
        try:
            num_episodes_val = int(num_episodes_val)
            if num_episodes_val < 1:
                num_episodes_val = 1
        except Exception:
            num_episodes_val = 1

    # Build RecordControlConfig (Phase 1 subset) with defaults for unspecified values
    cfg = RecordControlConfig(
        repo_id=config["repo_id"],
        single_task=config["single_task"],
        fps=fps_val,
        warmup_time_s=warmup_time_s,
        episode_time_s=episode_time_s,
        reset_time_s=reset_time_s,
        num_episodes=num_episodes_val,
        video=config.get("video", True),
        push_to_hub=config.get("push_to_hub", False),
        private=config.get("private", False),
        tags=config.get("tags"),
        num_image_writer_processes=num_img_writer_proc,
        num_image_writer_threads_per_camera=num_img_writer_threads_per_cam,
        display_data=config.get("display_data", False),
        play_sounds=False,
        resume=config.get("resume", False),
        interactive=False,
        save_eval=True,
        root=config.get("root"),
    )

    # Ensure no None values in cfg to prevent TypeErrors
    if cfg.num_episodes is None:
        cfg.num_episodes = 1
    if cfg.episode_time_s is None:
        cfg.episode_time_s = 30.0
    if cfg.warmup_time_s is None:
        cfg.warmup_time_s = 10.0
    if cfg.reset_time_s is None:
        cfg.reset_time_s = 10.0
    if cfg.fps is None:
        cfg.fps = 30
    if cfg.video is None:
        cfg.video = True
    if cfg.push_to_hub is None:
        cfg.push_to_hub = False
    if cfg.private is None:
        cfg.private = False
    if cfg.resume is None:
        cfg.resume = False
    if cfg.display_data is None:
        cfg.display_data = False

    # Guard against concurrent teleoperation stopping hazards (optional)
    if aloha_state and aloha_state.get("active"):
        raise RuntimeError("Cannot start recording while teleoperation is active. Please stop teleoperation first.")

    robot, owned = _get_robot_instance()
    logger.info("Starting API recording using existing robot instance (owned=%s)", owned)

    events = ApiEventAdapter()
    stop_event = recording_worker.stop_event
    stop_event.clear()

    recording_worker.active = True
    recording_worker.cfg = cfg
    recording_worker.events = events
    recording_worker.episode_index = 0
    recording_worker.total_frames = 0
    recording_worker.episode_frames = 0
    recording_worker.episode_start_t = None
    with recording_worker.status_lock:
        recording_worker.phase = "transition"
        recording_worker.phase_start_t = None
        recording_worker.phase_total_s = None

    # Worker function replicating record() orchestration with adapter
    def _worker():
        try:
            # Create or load dataset
            # Handle existing root directory edge-cases early
            try:
                from pathlib import Path
                root_path = Path(cfg.root) if cfg.root is not None else None
                if root_path and root_path.exists():
                    if not cfg.resume:
                        # If empty directory, remove it so LeRobot can create it
                        if root_path.is_dir() and not any(root_path.iterdir()):
                            try:
                                root_path.rmdir()
                                logger.info("Removed empty dataset root to allow creation: %s", root_path)
                            except Exception:
                                pass
                        else:
                            # If it looks like an existing dataset, auto-switch to resume
                            if (root_path / "meta" / "info.json").exists():
                                logger.info("Existing dataset detected at %s; switching to resume mode", root_path)
                                cfg.resume = True
                            else:
                                raise RuntimeError(
                                    f"Dataset root exists and is not empty: {root_path}. "
                                    "Choose a different root or enable Resume."
                                )
            except Exception as pre_e:
                raise

            if cfg.resume:
                dataset = LeRobotDataset(cfg.repo_id, root=cfg.root)
                if len(robot.cameras) > 0:
                    dataset.start_image_writer(
                        num_processes=cfg.num_image_writer_processes,
                        num_threads=cfg.num_image_writer_threads_per_camera * len(robot.cameras),
                    )
                sanity_check_dataset_robot_compatibility(dataset, robot, cfg.fps, cfg.video)
            else:
                sanity_check_dataset_name(cfg.repo_id, cfg.policy)
                dataset = LeRobotDataset.create(
                    cfg.repo_id,
                    cfg.fps,
                    root=cfg.root,
                    robot=robot,
                    use_videos=cfg.video,
                    image_writer_processes=cfg.num_image_writer_processes,
                    image_writer_threads=cfg.num_image_writer_threads_per_camera * len(robot.cameras),
                )

            recording_worker.dataset = dataset

            # Monkeypatch frame counting
            orig_add_frame = dataset.add_frame

            def add_frame_hook(frame):
                with recording_worker.status_lock:
                    recording_worker.total_frames += 1
                    recording_worker.episode_frames += 1
                return orig_add_frame(frame)

            dataset.add_frame = add_frame_hook  # type: ignore

            if not robot.is_connected:
                robot.connect()

            # Proactive camera preflight to surface RealSense issues early and clearly
            try:
                # Guard against None: pick a safe timeout derived from warmup or a minimum window
                warmup_timeout = cfg.warmup_time_s if cfg.warmup_time_s is not None else 10
                try:
                    warmup_timeout_int = int(warmup_timeout)
                except Exception:
                    warmup_timeout_int = 10
                _preflight_cameras(robot, timeout_s=min(10, max(3, warmup_timeout_int)))
            except Exception as cam_e:
                raise RuntimeError(
                    f"Camera preflight failed: {cam_e}. "
                    "Verify your Intel RealSense cameras stream frames (try 'realsense-viewer'), "
                    "ensure USB3 ports and cables, and that no other process is using the cameras."
                )

            # Warmup
            enable_teleoperation = True
            log_say("Warmup record", cfg.play_sounds)
            with recording_worker.status_lock:
                recording_worker.phase = "warmup"
                recording_worker.phase_total_s = float(cfg.warmup_time_s or 0)
                recording_worker.phase_start_t = time.perf_counter()
            warmup_record(
                robot,
                events,
                enable_teleoperation,
                cfg.warmup_time_s,
                cfg.display_data,
                cfg.fps,
            )

            if has_method(robot, "teleop_safety_stop"):
                robot.teleop_safety_stop()

            # Episodes loop
            while recording_worker.episode_index < cfg.num_episodes and not events["stop_recording"]:
                events.reset()
                with recording_worker.status_lock:
                    recording_worker.episode_frames = 0
                    recording_worker.episode_start_t = time.perf_counter()
                    recording_worker.phase = "recording"
                    recording_worker.phase_total_s = float(cfg.episode_time_s or 0)
                    recording_worker.phase_start_t = recording_worker.episode_start_t

                log_say(f"Recording episode {dataset.num_episodes}", cfg.play_sounds)
                record_episode(
                    robot=robot,
                    dataset=dataset,
                    events=events,
                    episode_time_s=cfg.episode_time_s,
                    display_data=cfg.display_data,
                    policy=None,  # Phase 1: no policy inference
                    fps=cfg.fps,
                    single_task=cfg.single_task,
                    interactive=False,
                )

                # Reset phase (skip for last unless rerecord). Snapshot rerecord to survive events.reset().
                rerecord_req = bool(events["rerecord_episode"])
                if not events["stop_recording"] and (
                    (recording_worker.episode_index < cfg.num_episodes - 1) or rerecord_req
                ):
                    log_say("Reset the environment", cfg.play_sounds)
                    # Clear exit_early etc. but preserve local rerecord_req for logic below
                    events.reset()
                    with recording_worker.status_lock:
                        recording_worker.phase = "resetting"
                        recording_worker.phase_total_s = float(cfg.reset_time_s or 0)
                        recording_worker.phase_start_t = time.perf_counter()
                    reset_environment(robot, events, cfg.reset_time_s, cfg.fps)

                if rerecord_req:
                    log_say("Re-record episode", cfg.play_sounds)
                    dataset.clear_episode_buffer()
                    # Do not advance episode index; restart same episode in next loop iteration
                    continue

                # Use episode_buffer size to determine if we captured any frames in this episode
                ep_size = 0
                try:
                    ep_size = int(getattr(dataset, "episode_buffer", {}).get("size", 0))
                except Exception:
                    ep_size = 0

                if ep_size > 0:
                    if cfg.save_eval:
                        # Indicate processing while saving episode (encoding, parquet, etc.)
                        with recording_worker.status_lock:
                            recording_worker.phase = "processing"
                            recording_worker.phase_total_s = None
                            recording_worker.phase_start_t = time.perf_counter()
                        dataset.save_episode()
                    recording_worker.episode_index += 1
                else:
                    log_say("No frames captured this episode, re-recording", cfg.play_sounds)
                    # If we ended up with no frames and no explicit rerecord request, force rerecord
                    # to avoid advancing the episode counter silently.
                    continue

            log_say("Stop recording", cfg.play_sounds, blocking=True)
            # Only disconnect if stopped manually; leave connected for resuming
            if events["stop_recording"]:
                core_stop_recording(robot, None, cfg.display_data)

            if cfg.push_to_hub:
                try:
                    # Indicate pushing phase without duration
                    with recording_worker.status_lock:
                        recording_worker.phase = "pushing"
                        recording_worker.phase_total_s = None
                        recording_worker.phase_start_t = time.perf_counter()
                    dataset.push_to_hub(tags=cfg.tags, private=cfg.private)
                except Exception as e:  # pragma: no cover
                    logger.warning(f"Push to hub failed: {e}")

        except Exception as e:
            logger.error(f"Recording worker error: {e}", exc_info=True)
            # Disconnect on error
            try:
                core_stop_recording(robot, None, cfg.display_data)
            except Exception:
                pass  # Ignore disconnect errors
            # Emit error event if possible
            sio = shared.get_socketio() if shared else None
            if sio:
                try:
                    coro = sio.emit("recording_error", {"error": str(e)})
                    _schedule_coro(coro)
                except Exception:
                    pass
        finally:
            with recording_worker.status_lock:
                recording_worker.active = False
                recording_worker.phase = "idle"
                recording_worker.phase_start_t = None
                recording_worker.phase_total_s = None
            # Final status emit
            sio = shared.get_socketio() if shared else None
            if sio:
                try:
                    coro = sio.emit("recording_status", recording_worker.snapshot())
                    _schedule_coro(coro)
                except Exception:
                    pass

    t = threading.Thread(target=_worker, name="RecordingWorker", daemon=True)
    recording_worker.thread = t
    t.start()


def stop_recording_via_api():
    if not recording_worker.active:
        return
    if recording_worker.events:
        recording_worker.events.set_flag("stop_recording", True)
        recording_worker.events.set_flag("exit_early", True)


## removed duplicate command_recording (see consolidated version below)


def _schedule_coro(coro):
    """Utility to schedule coroutine from threads."""
    try:
        loop = recording_worker.loop or asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, loop)
    except RuntimeError:
        pass


def _preflight_cameras(robot, timeout_s: int = 6):
    """Try to start camera streams and receive first frame within timeout.

    Raises with a clear error if frames don't arrive, to avoid cryptic thread errors later.
    """
    cams = getattr(robot, "cameras", {}) or {}
    if not cams:
        logger.warning("No cameras found on robot; proceeding without visual data.")
        return

    start = time.perf_counter()
    for name, cam in cams.items():
        try:
            # Ensure camera connected and fps set
            if not getattr(cam, "is_connected", False):
                cam.connect()
            # Kick off background reader and wait for first frame
            # Note: async_read() itself blocks until first frame or raises after ~1s*fps
            cam.async_read()
        except Exception as e:
            raise RuntimeError(f"Camera '{name}' failed to start: {e}")

    # All cams kicked; do a brief wait loop to ensure at least one frame arrived
    while time.perf_counter() - start < timeout_s:
        ready = True
        for name, cam in cams.items():
            if getattr(cam, "color_image", None) is None:
                ready = False
                break
        if ready:
            return
        time.sleep(0.1)

    # If here, at least one cam never produced a frame
    missing = [name for name, cam in cams.items() if getattr(cam, "color_image", None) is None]
    raise RuntimeError(f"No frames received within {timeout_s}s from cameras: {missing}")


async def _status_emitter_task(interval: float = 0.5):
    """Background task emitting status periodically."""
    sio = shared.get_socketio() if shared else None
    if not sio:
        logger.warning("Socket.IO not available for status emitter")
        return
    while True:
        try:
            if recording_worker.active:
                await sio.emit("recording_status", recording_worker.snapshot())
        except Exception:  # pragma: no cover
            pass
        await asyncio.sleep(interval)


def init_recording_worker(loop: asyncio.AbstractEventLoop):
    recording_worker.loop = loop
    # Start background status task once
    loop.create_task(_status_emitter_task())


def stop_recording_via_api():
    """Stop recording via API call"""
    if recording_worker.active and recording_worker.events:
        recording_worker.events.set_flag("stop_recording", True)
        logger.info("Recording stop requested via API")


def command_recording(action: str):
    """Handle recording commands via API"""
    if not recording_worker.active or not recording_worker.events:
        logger.warning(f"Recording command '{action}' ignored - no active recording")
        return
    
    if action == "exit_early":
        recording_worker.events.set_flag("exit_early", True)
        logger.info("Exit early command received")
    elif action == "rerecord_episode":
        recording_worker.events.set_flag("rerecord_episode", True)
        recording_worker.events.set_flag("exit_early", True)
        logger.info("Rerecord episode command received")
    elif action == "skip_episode":
        recording_worker.events.set_flag("exit_early", True)
        logger.info("Skip episode command received")
    elif action == "stop":
        recording_worker.events.set_flag("stop_recording", True)
        recording_worker.events.set_flag("exit_early", True)
        logger.info("Stop recording command received (exit_early also set)")
    else:
        logger.warning(f"Unknown recording command: {action}")


## removed duplicate helper and emitter definitions (see earlier implementations)


# Socket.IO event handler registration helpers
def register_socketio_handlers(sio):
    logger.info("Registering Socket.IO handlers for recording worker")
    @sio.event
    async def start_recording(sid, data):  # type: ignore
        try:
            logger.info(f"start_recording event received from {sid} with payload: {data}")
            start_recording_via_api(data or {})
            # Emit in two steps to pinpoint any serialization issues
            try:
                await sio.emit("recording_status", recording_worker.snapshot(), room=sid)
            except Exception as se:
                logger.error("start_recording status emit failed", exc_info=True)
                await sio.emit("recording_error", {"error": f"status_emit_failed: {se}"}, room=sid)
                return
            try:
                await sio.emit("recording_started", {"ok": True}, room=sid)
            except Exception as se:
                logger.error("start_recording started emit failed", exc_info=True)
                await sio.emit("recording_error", {"error": f"started_emit_failed: {se}"}, room=sid)
        except Exception as e:
            logger.error("start_recording error", exc_info=True)
            await sio.emit("recording_error", {"error": str(e)}, room=sid)

    @sio.event
    async def stop_recording(sid, data):  # type: ignore
        stop_recording_via_api()
        await sio.emit("recording_status", recording_worker.snapshot(), room=sid)

    @sio.event
    async def recording_command(sid, data):  # type: ignore
        try:
            action = (data or {}).get("action")
            logger.info(f"recording_command event '{action}' from {sid}")
            command_recording(action)
            await sio.emit("recording_status", recording_worker.snapshot())
        except Exception as e:
            logger.error(f"recording_command error: {e}")
            await sio.emit("recording_error", {"error": str(e)})
