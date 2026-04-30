/* ============================================
   Aether Studio — Client-Side Router
   History API routing with deep linking
   ============================================ */

const ROUTE_MAP = {
  'forge': 'generate',
  'vault': 'history',
  'tasks': 'tasks',
  'discovery': 'discovery',
  'feed': 'feed',
  'generate': 'generate',
  'history': 'history',
};

/**
 * Create a router bound to the app
 * @param {import('./store.js').AppState} state
 * @param {Function} setViewCallback - (viewName, pushState) => void
 * @param {Function} openByIdCallback - (requestId) => void
 * @returns {{ handleRouting: Function, navigateTo: Function }}
 */
export function createRouter(state, setViewCallback, openByIdCallback) {
  
  function handleRouting() {
    const path = window.location.pathname.replace(/^\//, '') || 'forge';
    const segments = path.split('/');
    const baseView = segments[0];

    const view = ROUTE_MAP[baseView] || 'generate';
    setViewCallback(view, false);

    // Deep linking: /view/{id}
    if (baseView === 'view' && segments[1]) {
      openByIdCallback(segments[1]);
    }
  }

  function navigateTo(view) {
    const path = Object.keys(ROUTE_MAP).find(k => ROUTE_MAP[k] === view) || view;
    if (path !== window.location.pathname.replace(/^\//, '')) {
      history.pushState({ view }, '', '/' + path);
    }
  }

  // Listen for back/forward navigation
  window.addEventListener('popstate', () => handleRouting());

  return { handleRouting, navigateTo, ROUTE_MAP };
}
