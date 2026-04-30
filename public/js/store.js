/* ============================================
   Aether Studio — AppState
   Centralized reactive state management
   ============================================ */

export class AppState {
  #data = {};
  #listeners = new Map();
  #persistMap = new Map();

  constructor(initial = {}) {
    this.#data = this.#deepClone(initial);
  }

  /**
   * Get a value by dot-notation path
   * @param {string} path - e.g. 'vault.realmFilter'
   * @returns {*}
   */
  get(path) {
    return path.split('.').reduce((obj, key) => obj?.[key], this.#data);
  }

  /**
   * Set a value by dot-notation path, notify subscribers
   * @param {string} path - e.g. 'vault.cursor'
   * @param {*} value
   */
  set(path, value) {
    const keys = path.split('.');
    const last = keys.pop();
    let obj = this.#data;

    for (const key of keys) {
      if (obj[key] === undefined || obj[key] === null) {
        obj[key] = {};
      }
      obj = obj[key];
    }

    const oldValue = obj[last];
    obj[last] = value;

    // Persist if configured
    if (this.#persistMap.has(path)) {
      try {
        localStorage.setItem(this.#persistMap.get(path), JSON.stringify(value));
      } catch (e) { /* quota exceeded, ignore */ }
    }

    // Notify exact match listeners
    this.#notify(path, value, oldValue);

    // Notify wildcard parent listeners (e.g., 'vault.*' fires for 'vault.cursor')
    const parentPath = keys.join('.');
    if (parentPath) {
      this.#notify(parentPath + '.*', { path, value, oldValue });
    }
  }

  /**
   * Subscribe to changes on a path
   * @param {string} path - e.g. 'vault.realmFilter' or 'vault.*'
   * @param {Function} callback - (newValue, oldValue) => void
   * @returns {Function} unsubscribe
   */
  subscribe(path, callback) {
    if (!this.#listeners.has(path)) {
      this.#listeners.set(path, new Set());
    }
    this.#listeners.get(path).add(callback);

    return () => {
      const set = this.#listeners.get(path);
      if (set) {
        set.delete(callback);
        if (set.size === 0) this.#listeners.delete(path);
      }
    };
  }

  /**
   * Configure auto-persistence to localStorage
   * @param {string} path - state path
   * @param {string} storageKey - localStorage key
   */
  persist(path, storageKey) {
    this.#persistMap.set(path, storageKey);

    // Hydrate from localStorage on setup
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored !== null) {
        this.set(path, JSON.parse(stored));
      }
    } catch (e) { /* ignore parse errors */ }
  }

  /**
   * Get the entire state tree (for debugging)
   */
  getAll() {
    return this.#deepClone(this.#data);
  }

  /**
   * Batch update multiple paths without triggering per-path notifications
   * Fires a single 'batch' event at the end
   */
  batch(updates) {
    for (const [path, value] of Object.entries(updates)) {
      const keys = path.split('.');
      const last = keys.pop();
      let obj = this.#data;
      for (const key of keys) {
        if (obj[key] === undefined) obj[key] = {};
        obj = obj[key];
      }
      obj[last] = value;
    }
    this.#notify('__batch__', updates);
  }

  // === Private Methods ===

  #notify(path, newValue, oldValue) {
    const listeners = this.#listeners.get(path);
    if (listeners) {
      for (const cb of listeners) {
        try { cb(newValue, oldValue); } catch (e) { console.error('[AppState] Listener error:', e); }
      }
    }
  }

  #deepClone(obj) {
    if (obj === null || typeof obj !== 'object') return obj;
    if (obj instanceof Set) return new Set(obj);
    if (obj instanceof Map) return new Map(obj);
    if (Array.isArray(obj)) return obj.map(v => this.#deepClone(v));
    const clone = {};
    for (const [k, v] of Object.entries(obj)) {
      clone[k] = this.#deepClone(v);
    }
    return clone;
  }
}

/**
 * Create the global app state with defaults
 */
export function createAppState() {
  const state = new AppState({
    app: {
      mode: 'standard',
      activeRequestId: '',
      serverUrl: window.location.origin,
      isGenerating: false,
      isTabVisible: true,
      activeView: 'generate',
      currentPoll: null,
      etagCache: {},
    },
    auth: {
      uid: 'uid_0',
      user: null,
    },
    vault: {
      realmFilter: 'all',
      showHidden: false,
      selectionMode: false,
      selectedIds: new Set(),
      cursor: null,
      hasMore: true,
      loading: false,
      loaded: false,
      limit: 20,
    },
    discovery: {
      cursor: null,
      hasMore: true,
      loading: false,
      items: [],
    },
    feed: {
      cursor: null,
      hasMore: true,
      loading: false,
      items: [],
    },
    matrix: {
      paused: false,
      cancelled: false,
    },
    forge: {
      pendingDeletions: new Set(),
      activePolls: new Set(),
    },
    lightbox: {
      data: null,
      currentUrl: null,
      currentIndex: 0,
      currentHidden: false,
    },
  });

  // Configure localStorage persistence
  state.persist('app.mode', 'a_mode');
  state.persist('app.activeRequestId', 'a_active_request_id');

  return state;
}
