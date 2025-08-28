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
    from .robot import robot_service  # type: ignore
except Exception:  # pragma: no cover
    robot_service = None

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
            return {
                "active": self.active,
                "episode_index": self.episode_index,
                "total_episodes": getattr(self.cfg, "num_episodes", None),
                "episode_frames": self.episode_frames,
                "total_frames": self.total_frames,
                "episode_elapsed_s": episode_elapsed,
                "episode_duration_s": getattr(self.cfg, "episode_time_s", None),
                "repo_id": getattr(self.cfg, "repo_id", None),
                "single_task": getattr(self.cfg, "single_task", None),
                "fps_target": getattr(self.cfg, "fps", None),
                # fps_current simple estimate: frames / elapsed
                "fps_current": (
                    (self.episode_frames / episode_elapsed) if episode_elapsed and episode_elapsed > 0 else None
                ),
                "state": (
                    "recording_episode"
                    if self.active and self.events and not self.events.get("exit_early", False)
                    else ("idle" if not self.active else "transition")
                ),
            }


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
    # Robot service reuse
    if robot_service and getattr(robot_service, "robot", None) is not None:
        robot = robot_service.robot
        try:
            if robot and robot.is_connected:
                return robot, False
        except Exception:  # pragma: no cover
            pass
    # Otherwise fail (Phase 1: no autonomous robot creation here)
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

    # Build RecordControlConfig (Phase 1 subset) with defaults for unspecified values
    cfg = RecordControlConfig(
        repo_id=config["repo_id"],
        single_task=config["single_task"],
        fps=config.get("fps"),
        warmup_time_s=config.get("warmup_time_s", 2),
        episode_time_s=config.get("episode_time_s", 30),
        reset_time_s=config.get("reset_time_s", 10),
        num_episodes=config.get("num_episodes", 1),
        video=config.get("video", True),
        push_to_hub=config.get("push_to_hub", False),
        private=config.get("private", False),
        tags=config.get("tags"),
        num_image_writer_processes=config.get("num_image_writer_processes", 0),
        num_image_writer_threads_per_camera=config.get("num_image_writer_threads_per_camera", 4),
        display_data=config.get("display_data", False),
        play_sounds=False,
        resume=config.get("resume", False),
        interactive=False,
        save_eval=True,
        root=config.get("root"),
    )

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

    # Worker function replicating record() orchestration with adapter
    def _worker():
        try:
            # Create or load dataset
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

            # Warmup
            enable_teleoperation = True
            log_say("Warmup record", cfg.play_sounds)
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

                # Reset phase (skip for last unless rerecord)
                if not events["stop_recording"] and (
                    (recording_worker.episode_index < cfg.num_episodes - 1) or events["rerecord_episode"]
                ):
                    log_say("Reset the environment", cfg.play_sounds)
                    events.reset()
                    reset_environment(robot, events, cfg.reset_time_s, cfg.fps)

                if events["rerecord_episode"]:
                    log_say("Re-record episode", cfg.play_sounds)
                    dataset.clear_episode_buffer()
                    continue

                if len(dataset) > 0:
                    if cfg.save_eval:
                        dataset.save_episode()
                    recording_worker.episode_index += 1
                else:
                    log_say("Dataset is empty, re-record episode", cfg.play_sounds)

            log_say("Stop recording", cfg.play_sounds, blocking=True)
            core_stop_recording(robot, None, cfg.display_data)

            if cfg.push_to_hub:
                try:
                    dataset.push_to_hub(tags=cfg.tags, private=cfg.private)
                except Exception as e:  # pragma: no cover
                    logger.warning(f"Push to hub failed: {e}")

        except Exception as e:
            logger.error(f"Recording worker error: {e}", exc_info=True)
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


def command_recording(action: str):
    if not recording_worker.active or not recording_worker.events:
        raise RuntimeError("No active recording session")
    ev = recording_worker.events
    if action == "rerecord_episode":
        ev.set_flag("rerecord_episode", True)
        ev.set_flag("exit_early", True)
    elif action == "skip_episode":
        ev.set_flag("exit_early", True)
    elif action == "stop":
        stop_recording_via_api()
    else:
        raise ValueError(f"Unknown recording command: {action}")


def _schedule_coro(coro):
    """Utility to schedule coroutine from threads."""
    try:
        loop = recording_worker.loop or asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, loop)
    except RuntimeError:
        pass


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


# Socket.IO event handler registration helpers
def register_socketio_handlers(sio):
    @sio.event
    async def start_recording(sid, data):  # type: ignore
        try:
            start_recording_via_api(data or {})
            await sio.emit("recording_status", recording_worker.snapshot(), room=sid)
            await sio.emit("recording_started", {"ok": True}, room=sid)
        except Exception as e:
            await sio.emit("recording_error", {"error": str(e)}, room=sid)

    @sio.event
    async def stop_recording(sid, data):  # type: ignore
        stop_recording_via_api()
        await sio.emit("recording_status", recording_worker.snapshot(), room=sid)

    @sio.event
    async def recording_command(sid, data):  # type: ignore
        try:
            action = (data or {}).get("action")
            command_recording(action)
            await sio.emit("recording_status", recording_worker.snapshot())
        except Exception as e:
            await sio.emit("recording_error", {"error": str(e)})
