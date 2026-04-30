/* ============================================
   Aether Studio — Toast Component
   Footer status notifications
   ============================================ */

import { $ } from '../utils/dom.js';

let toastTimer = null;

/**
 * Show a toast notification
 * @param {string} msg
 * @param {string} kind - 'info' | 'error' | 'success'
 */
export function showToast(msg, kind = 'info') {
  const el = $('#footerStatus');
  if (!el) return;

  el.textContent = msg;
  el.style.borderColor = kind === 'error' 
    ? 'rgba(239,68,68,0.35)' 
    : 'var(--panel-border)';

  el.classList.add('is-visible');

  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    el.classList.remove('is-visible');
  }, 3200);
}
