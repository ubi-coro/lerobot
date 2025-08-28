import { defineStore } from 'pinia';
import { useRobotStore } from './robotStore';

// Simple field validation helper
function validateConfig(cfg) {
  const errors = {};
  if (!cfg.repo_id || !cfg.repo_id.includes('/')) errors.repo_id = 'Format: user/dataset';
  if (!cfg.single_task || cfg.single_task.trim().length < 3) errors.single_task = 'Describe the task';
  if (!cfg.fps || cfg.fps <= 0) errors.fps = 'FPS > 0';
  if (!cfg.episode_time_s || cfg.episode_time_s < 1) errors.episode_time_s = '>=1s';
  if (!cfg.num_episodes || cfg.num_episodes < 1) errors.num_episodes = '>=1';
  if (!cfg.root || cfg.root.trim().length === 0) errors.root = 'Root path required';
  return errors;
}

export const useRecordingStore = defineStore('recording', {
  state: () => ({
    config: {
      repo_id: '',
      single_task: '',
      fps: 30,
      warmup_time_s: 2,
      episode_time_s: 30,
      reset_time_s: 10,
      num_episodes: 1,
  // video always on for dataset recording; no toggle needed (backend assumes video)
      push_to_hub: false,
      private: false,
      resume: false,
  root: '',
  display_data: false
    },
    status: {
      active: false,
      episode_index: 0,
      total_episodes: 0,
      episode_frames: 0,
      total_frames: 0,
      episode_elapsed_s: null,
      episode_duration_s: null,
      fps_target: null,
      fps_current: null,
      state: 'idle'
    },
    starting: false,
    error: null,
    validationErrors: {},
    lastUpdate: null,
    initializedSocket: false
  }),
  getters: {
    isActive: (s) => s.status.active,
    isIdle: (s) => !s.status.active,
    canStart: (s) => Object.keys(s.validationErrors).length === 0 && !s.status.active && !s.starting,
    progressPct: (s) => {
      if (!s.status.total_episodes || s.status.total_episodes === 0) return 0;
      return Math.min(100, Math.round((s.status.episode_index / s.status.total_episodes) * 100));
    },
    episodeProgressPct: (s) => {
      if (!s.status.episode_duration_s || !s.status.episode_elapsed_s) return 0;
      return Math.min(100, Math.round((s.status.episode_elapsed_s / s.status.episode_duration_s) * 100));
    }
  },
  actions: {
    _initPersistence() {
      // load saved root if present and none set
      const savedRoot = localStorage.getItem('lerobot.recording.root');
      if (savedRoot && !this.config.root) {
        this.config.root = savedRoot;
        this.validationErrors = validateConfig(this.config);
      }
    },
    ensureSocketListeners() {
      if (this.initializedSocket) return;
      const robotStore = useRobotStore();
      robotStore.initSocket();
      const sock = robotStore.socket;
      if (!sock) return;
      sock.on('recording_status', (payload) => {
        if (!payload) return;
        this.status = { ...this.status, ...payload };
        this.status.active = !!(payload.active);
        this.lastUpdate = Date.now();
      });
      sock.on('recording_error', (payload) => {
        this.error = payload?.error || 'Unknown recording error';
      });
      sock.on('recording_started', () => {
        this.starting = false;
        this.status.active = true;
      });
      this.initializedSocket = true;
    },
    updateConfig(partial) {
      this.config = { ...this.config, ...partial };
      // If push_to_hub was turned off, also clear private flag to avoid stale state
      if (!this.config.push_to_hub && this.config.private) {
        this.config.private = false;
      }
      this.validationErrors = validateConfig(this.config);
      if (typeof partial.root !== 'undefined') {
        try { localStorage.setItem('lerobot.recording.root', this.config.root || ''); } catch (_) { /* ignore */ }
      }
    },
    validateAll() {
      this.validationErrors = validateConfig(this.config);
      return Object.keys(this.validationErrors).length === 0;
    },
    start() {
      const robotStore = useRobotStore();
      this.ensureSocketListeners();
      if (!robotStore.isConnected) {
        this.error = 'Robot not connected';
        return;
      }
      if (!this.validateAll()) return;
      const sock = robotStore.socket;
      if (!sock) {
        this.error = 'Socket unavailable';
        return;
      }
      this.starting = true;
      this.error = null;
  const payload = { ...this.config };
  // enforce video true implicitly
  payload.video = true;
      sock.emit('start_recording', payload);
    },
    stop() {
      const robotStore = useRobotStore();
      const sock = robotStore.socket;
      if (sock) sock.emit('stop_recording', {});
    },
    rerecordEpisode() {
      const sock = useRobotStore().socket; if (sock) sock.emit('recording_command', { action: 'rerecord_episode' });
    },
    skipEpisode() {
      const sock = useRobotStore().socket; if (sock) sock.emit('recording_command', { action: 'skip_episode' });
    },
    emergencyStop() {
      const sock = useRobotStore().socket; if (sock) sock.emit('recording_command', { action: 'stop' });
    },
    resetForm() {
      this.config = { ...this.config, repo_id: '', single_task: '' };
      this.validationErrors = {};
    }
  }
});

// Initialize persistence side-effect when store is first created
const _store = useRecordingStore?.();
if (_store && typeof _store._initPersistence === 'function') {
  _store._initPersistence();
}
