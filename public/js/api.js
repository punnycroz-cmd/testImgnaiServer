/* ============================================
   Aether Studio — API Module
   Centralized fetch with ETag caching
   ============================================ */

/**
 * Create an API client bound to app state
 * @param {import('./store.js').AppState} state
 * @returns {{ apiFetch: Function }}
 */
export function createApiClient(state) {
  
  /**
   * Fetch from the backend API with ETag support
   * @param {string} path - API path (e.g. '/health')
   * @param {RequestInit} opts - fetch options
   * @returns {Promise<*>} parsed JSON response, or null for 304
   */
  async function apiFetch(path, opts = {}) {
    let serverUrl = state.get('app.serverUrl') || 'https://f70cef08-b1c6-4363-88e3-774e02123f6e-00-1btn7n40xrnba.kirk.replit.dev';
    
    // Safety: If it's still pointing to pages.dev, force the Replit URL
    if (serverUrl.includes('pages.dev')) {
      serverUrl = 'https://f70cef08-b1c6-4363-88e3-774e02123f6e-00-1btn7n40xrnba.kirk.replit.dev';
    }
    
    if (!serverUrl || serverUrl.startsWith('file://')) {
      console.warn('Invalid server URL or file:// protocol. Skipping fetch:', path);
      throw new Error('Local File Protocol detected. Please run via a web server.');
    }

    try {
      const fetchOpts = {
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': 'no-cache',
          'Pragma': 'no-cache',
          ...opts.headers,
        },
        credentials: 'include',
        cache: 'no-store',
        ...opts,
      };

      // Build clean URL
      const cleanServer = serverUrl.replace(/\/+$/, '');
      const cleanPath = path.startsWith('/') ? path : `/${path}`;
      const finalUrl = `${cleanServer}${cleanPath}`;

      // Backup header injection for cursor/hidden params
      if (finalUrl.includes('before=')) {
        const match = finalUrl.match(/[?&]before=([^&]+)/);
        if (match) fetchOpts.headers['X-Debug-Cursor'] = match[1];
      }
      if (finalUrl.includes('include_hidden=')) {
        const match = finalUrl.match(/[?&]include_hidden=([^&]+)/);
        if (match) fetchOpts.headers['X-Include-Hidden'] = match[1];
      }

      const resp = await fetch(finalUrl, fetchOpts);
      const text = await resp.text();
      let data = null;
      try { data = text ? JSON.parse(text) : null; } catch { data = { raw: text }; }

      if (!resp.ok) {
        const err = new Error(data?.detail || data?.error || `HTTP ${resp.status}`);
        err.data = data;
        throw err;
      }

      return data;
    } catch (e) {
      console.error('apiFetch error:', e);
      throw e;
    }
  }

  return { apiFetch };
}
