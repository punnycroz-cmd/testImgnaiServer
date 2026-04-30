/* ============================================
   Aether Studio — Modal Component
   Confirm dialog
   ============================================ */

import { $ } from '../utils/dom.js';

let activeResolver = null;

/**
 * Show a confirm dialog
 * @param {string} title
 * @param {string} message
 * @param {Function} onConfirm
 */
export function openConfirm(title, message, onConfirm) {
  const modal = $('#confirmModal');
  const titleEl = $('#confirmTitle');
  const msgEl = $('#confirmMsg');
  const yesBtn = $('#confirmYes');

  if (titleEl) titleEl.textContent = title;
  if (msgEl) msgEl.textContent = message;

  // Clone to remove old listeners
  if (yesBtn) {
    const newYes = yesBtn.cloneNode(true);
    yesBtn.parentNode.replaceChild(newYes, yesBtn);
    newYes.id = 'confirmYes';
    newYes.onclick = () => {
      onConfirm();
      closeConfirm();
    };
  }

  if (modal) {
    modal.classList.add('is-open');
  }
}

/**
 * Close the confirm dialog
 */
export function closeConfirm() {
  const modal = $('#confirmModal');
  if (modal) {
    modal.classList.remove('is-open');
  }
}

// Expose globally for inline HTML usage during transition
window.closeConfirm = closeConfirm;
