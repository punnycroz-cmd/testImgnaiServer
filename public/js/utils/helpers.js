/* ============================================
   Aether Studio — Helper Utilities
   ============================================ */

/**
 * Async sleep
 * @param {number} ms
 * @returns {Promise<void>}
 */
export function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Exponential backoff delay for polling
 * @param {number} attempt
 * @param {boolean} isStarRealm
 * @returns {number} milliseconds
 */
export function backoffDelay(attempt, isStarRealm = false) {
  if (isStarRealm) return 40000;
  return Math.min(8000, 2000 + (attempt * 300));
}

/**
 * Check if a server URL placeholder is unresolved
 */
export function isUnresolved(v) {
  return !v || v.startsWith('__') || v.includes('REPLACE');
}

/**
 * Resolve server URL based on mode
 */
export function resolveServerUrl(mode) {
  const std = isUnresolved(window.__SERVER_URL__)
    ? window.location.origin
    : window.__SERVER_URL__;
  const nsfw = isUnresolved(window.__SERVER_URL_NSFW__)
    ? std
    : window.__SERVER_URL_NSFW__;
  return (mode === 'nsfw' ? nsfw : std).replace(/\/$/, '');
}

/**
 * Debounce a function
 * @param {Function} fn
 * @param {number} delay - milliseconds
 * @returns {Function}
 */
export function debounce(fn, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

/**
 * Throttle a function
 * @param {Function} fn
 * @param {number} limit - milliseconds
 * @returns {Function}
 */
export function throttle(fn, limit) {
  let inThrottle;
  return (...args) => {
    if (!inThrottle) {
      fn(...args);
      inThrottle = true;
      setTimeout(() => { inThrottle = false; }, limit);
    }
  };
}
