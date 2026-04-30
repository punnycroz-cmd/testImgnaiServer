/* ============================================
   Aether Studio — Event Delegation
   ============================================ */

/**
 * Delegated event system — one listener per container
 */
export const EventDelegate = {
  /**
   * Register a delegated event listener
   * @param {HTMLElement} container - Parent element to listen on
   * @param {string} eventType - e.g. 'click'
   * @param {string} selector - CSS selector to match children
   * @param {Function} handler - (event, matchedElement) => void
   * @returns {Function} cleanup function
   */
  on(container, eventType, selector, handler) {
    const listener = (e) => {
      const target = e.target.closest(selector);
      if (target && container.contains(target)) {
        handler(e, target);
      }
    };
    container.addEventListener(eventType, listener);
    return () => container.removeEventListener(eventType, listener);
  },
};
