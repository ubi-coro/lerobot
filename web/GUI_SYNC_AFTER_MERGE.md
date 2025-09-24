# GUI + Backend Sync After Merge (2025-09-19)

This document summarizes the current state after merging latest `lerobot` core and `gui-experimental`, and outlines what to do to get the GUI and project running again.

## TL;DR
- Backend has two paths: a modular FastAPI app with REST routers and a Socket.IO recording worker.
- Frontend currently uses Socket.IO for recording control/status (working path) and some REST calls under `/api/dataset` for browsing.
- Action: keep Socket.IO-based recording control; align any REST calls used by the GUI with the available routers.

## Current Backend Surface

- Entrypoints:
  - `web/backend_fastapi/main_modular.py` (preferred modern app)
    - Routers mounted: `robot`, `teleoperation`, `safety`, `monitoring`, `recording`, `configuration`, `dataset` (prefixed `/api/dataset`).
    - Socket.IO: handlers registered via `modules/recording_worker.register_socketio_handlers(sio)`.
    - Background tasks: teleop status broadcaster; event loop stored for worker.
  - `web/backend_fastapi/main.py` (legacy app keeping GUI recording worker import indirection; can be removed once modular is final).

- Recording control (Socket.IO):
  - Events emitted by frontend store:
    - `start_recording` with payload (config)
    - `stop_recording`
    - `recording_command` with `{action: 'rerecord_episode'|'skip_episode'|'stop'|'exit_early'}`
  - Events emitted by backend:
    - `recording_status` — periodic updates and immediate snapshots
    - `recording_started` — ack after start
    - `recording_error` — error string

- Dataset browsing/visualization (REST):
  - Base: `/api/dataset`
  - `GET /api/dataset/browse`
  - `POST /api/dataset/visualize`
  - `POST /api/dataset/browse-directory` — folder picker backend
  - `GET /api/dataset/visualization/status`

## Current Frontend Surface

- Socket client at `robotStore.initSocket()` (src/stores/robotStore.js)
  - Connects to `${VITE_BACKEND_URL || location.origin}` path `/socket.io`
  - Subscribes to: `teleoperation_status`, camera frames/list, etc.
  - Recording UI (src/stores/recordingStore.js) uses the same socket (via `useRobotStore().socket`) to emit `start_recording`, `stop_recording`, `recording_command` and consumes `recording_status`, `recording_started`, `recording_error`.
- Dataset REST client at `src/services/api/datasetApi.js` points to `/api/dataset` and uses the endpoints listed above.

## Mismatches to Address

- Ensure the running backend uses `main_modular.py` (or equivalent) where:
  - `register_socketio_handlers(sio)` is called — required for GUI recording.
  - Routers include `dataset_router` with prefix `/api/dataset` — required for folder picker and dataset browsing.
- Remove/avoid stale references to older REST endpoints like `/record/start` (front-end `datasetApi.js` already uses `/api/dataset` for non-recording features; recording itself uses Socket.IO — correct).
- pyproject.toml cleanup — fix duplicate tables and invalid keys as per prior guidance to ensure `pip install -e .` works.

## Run Instructions

- Backend (FastAPI + Socket.IO):
  - From repo root or `web/backend_fastapi`, run one of:
    - `python -m uvicorn web.backend_fastapi.main_modular:socket_app --host 0.0.0.0 --port 8000 --reload`
    - If sticking to `main.py` for now: `python -m uvicorn web.backend_fastapi.main:socket_app --host 0.0.0.0 --port 8000 --reload`
  - Confirm health: `GET http://localhost:8000/api/health`

- Frontend (Vite):
  - `cd web/frontend`
  - `npm install`
  - `VITE_BACKEND_URL=http://localhost:8000 npm run dev`

- Robot service:
  - Ensure a robot is connected via your usual path. The recording worker expects a connected robot from either teleoperation or the robot service.

## Feature Parity/Checklist

Recording via GUI:
- [x] Manual Resume toggle required; backend enforces error if dataset exists without resume.
- [x] Status UI shows phase, FPS, frames; final episode count after completion.
- [x] Socket events aligned (`start_recording`, `recording_started`, `recording_status`, `recording_error`).

Dataset/folder picker:
- [x] Folder picker uses `/api/dataset/browse-directory`.
- [x] Browse datasets via `/api/dataset/browse`.

Teleoperation telemetry:
- [x] Periodic `teleoperation_status` broadcast.

## Post-Merge Action Plan

1) Backend boot selection
- Decide on `main_modular.py` as the canonical backend. Update any docs/scripts to start this app.

2) Socket.IO registration verification
- Verify `register_socketio_handlers(sio)` is called (already in `main_modular.py`). If you use `main.py`, confirm it imports worker and registers handlers similarly.

3) Recording Worker compatibility audit
- We already updated `recording_worker.py` to:
  - Require manual `resume` when an existing dataset is detected.
  - Emit `existing_episodes` and `final_episodes` in status.
- Validate no upstream API signature changes (fps, warmup/reset, etc.). Adjust payload mapping if needed.

4) Frontend alignment
- Confirm `RecordDatasetView.vue` shows the new totals and resume UX.
- Confirm `robotStore.initSocket()` connects to the right backend URL (set `VITE_BACKEND_URL`).
- Remove any dead code in `src/services/socket.js` or ensure it’s either used or deleted.

5) pyproject.toml hygiene
- Merge duplicate `[tool.setuptools.packages.find]` and `[project.scripts]` tables.
- Ensure `where = ["src"]` lives under `[tool.setuptools.packages.find]` only.
- `pip install -e .` should work again.

6) Smoke tests
- Start backend (`main_modular.py`).
- Start frontend (Vite dev). Connect robot or simulator.
- Start recording with a fresh root → progresses. Try existing dataset without Resume → error surfaces. With Resume → progresses. After finish, final total shown.

## Core changes: Robot/Teleoperation configs (no "aloha")

Upstream `lerobot` core consolidated robot and teleoperation creation through config dataclasses and factory functions, and removed legacy "aloha" variants from public config entry points.

- New entry points (see `src/lerobot/teleoperate.py`):
  - `RobotConfig` and `make_robot_from_config(cfg.robot)`
  - `TeleoperatorConfig` and `make_teleoperator_from_config(cfg.teleop)`
  - `TeleoperateConfig` drives teleop loop: `{ teleop: TeleoperatorConfig, robot: RobotConfig, fps, teleop_time_s, display_data }`
- Available robot types (folders under `src/lerobot/robots/`):
  - `so101_follower`, `so100_follower`, `bi_so100_follower`, `koch_follower`, `hope_jr`, `lekiwi`, `reachy2`, `stretch3`, `viperx`, etc.
- Available teleoperators (folders under `src/lerobot/teleoperators/`):
  - `so101_leader`, `so100_leader`, `bi_so100_leader`, `koch_leader`, `gamepad`, `homunculus`, `reachy2_teleoperator`, `stretch3_gamepad`, `widowx`, etc.

Implications for the GUI and backend services:

- The previous GUI default `selectedRobotType: 'aloha'` is invalid and must be updated (e.g., `so101_follower`).
- Teleoperation start/stop endpoints in the backend should build `RobotConfig` and `TeleoperatorConfig` objects and call the upstream factories, not any deprecated aloha-specific code.
- The Teleoperation UI should generate structured config for both robot and teleop:
  - Robot ports can vary by type (e.g., left/right arm ports for bimanual, single `port` for single-arm, or network/USB identifiers).
  - Camera config fits the upstream camera configs (`opencv` or `realsense`). Provide form fields and serialize to the expected structure.
  - Expose `fps`, optional `teleop_time_s`, and `display_data` as in `TeleoperateConfig`.

We’ll add a backend helper to list supported robot/teleop types and their required fields to drive dynamic forms in the GUI (introspect modules or ship a static manifest).

## Concrete Punch List (prioritized)

High
- Backend: implement teleoperation create/connect using new factories:
  - ✅ Add/confirm endpoints that accept `{ robot: RobotConfig, teleop: TeleoperatorConfig, fps, teleop_time_s, display_data }` and use `make_*_from_config()`.
  - ✅ Remove/guard any leftover aloha-specific paths.
- Frontend Teleoperation UI:
  - Update the Robot/Teleop selectors to offer the new types listed above.
  - Map UI fields to `RobotConfig` and `TeleoperatorConfig` (ports, ids, camera configs). Provide presets for common robots (so101/so100/bi_so100).
- Verify Socket.IO recording flow still works with robot connected via new teleop path.

Medium
- Backend: endpoint to enumerate supported robot/teleop types and expected fields (introspection or manifest) for dynamic GUI forms.
- Frontend: dynamic form rendering based on the manifest; validation hints (e.g., missing left/right ports for bi-manual).
- ✅ Config file: Create `~/.config/lerobot/hardware_config.json` with workstation-specific ports/calibration.
- Docs: update screenshots/text removing "aloha"; add examples for `so101_follower` + `so101_leader`.

Low
- Add a dataset existence preflight REST API to remove UI heuristics entirely.
- Add toasts/snackbars for `recording_error` and important state changes.
- Remove unused `src/services/socket.js` if we keep socket management in stores.

## Known Gaps / Nice-to-haves
- A REST preflight endpoint to check dataset existence instead of UI heuristics.
- A visible snackbar/toast for `recording_error` messages.
- One-click link from UI to backend API docs (`/docs`/`/redoc`).

## Troubleshooting
- If Start seems to do nothing:
  - Check browser console for `recording_error`.
  - Confirm socket connected and `recording_started` event arrives after start.
  - Ensure robot is connected (`robotStore.isConnected === true`).
- If folder picker can’t browse:
  - Verify `POST /api/dataset/browse-directory` works in curl.
- If install fails:
  - Fix duplicate/stray keys in `pyproject.toml` and re-run `pip install -e .`.

---

Last updated: 2025-09-19
