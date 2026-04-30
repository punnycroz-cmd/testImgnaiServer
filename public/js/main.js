/* ============================================
   Aether Studio — Main Entry Point
   Wires all modules together
   ============================================ */

import { createAppState } from './store.js';
import { createApiClient } from './api.js';
import { createRouter } from './router.js';
import { showToast } from './components/Toast.js';
import { openConfirm, closeConfirm } from './components/Modal.js';
import { createLightbox } from './components/Lightbox.js';
import { createAuthService } from './services/auth.js';
import { initAetherCanvas } from './services/particles.js';
import { createForgeView } from './views/Forge.js';
import { createVaultView } from './views/Vault.js';
import { createDiscoveryView } from './views/Discovery.js';
import { createFeedView } from './views/Feed.js';

// ── Bootstrap ──────────────────────────────────
const state = createAppState();
const api = createApiClient(state);
const toast = showToast;

// ── Initialize Modules ─────────────────────────
const lightbox = createLightbox(state, api, toast);
const forge = createForgeView(state, api, toast);
const vault = createVaultView(state, api, toast, lightbox.open);
const discovery = createDiscoveryView(state, api, toast, vault.createBatchCard);
const feed = createFeedView(state, api, toast);
const auth = createAuthService(state, api, toast);

// Observer references
let vaultObs = null, discoveryObs = null, feedObs = null;

// ── View Switching ─────────────────────────────
function setView(v, pushState = true) {
  if (pushState) router.navigateTo(v);
  document.querySelectorAll('.view').forEach(el => { el.classList.remove('active'); el.classList.add('hidden'); });
  const viewEl = document.getElementById(`view-${v}`);
  if (viewEl) { viewEl.classList.remove('hidden'); void viewEl.offsetWidth; viewEl.classList.add('active'); }
  document.querySelectorAll('[data-view]').forEach(b => {
    const match = b.dataset.view === v;
    b.classList.toggle('active', match);
    b.classList.toggle('opacity-100', match);
    b.classList.toggle('opacity-60', !match);
  });
  const mainEl = document.querySelector('main');
  if (mainEl) mainEl.scrollTo({ top: 0, behavior: 'smooth' });
  state.set('app.activeView', v);

  // Cleanup old observers
  if (vaultObs) { vaultObs.disconnect(); vaultObs = null; }
  if (discoveryObs) { discoveryObs.disconnect(); discoveryObs = null; }
  if (feedObs) { feedObs.disconnect(); feedObs = null; }

  if (v === 'history') { vault.render(); vaultObs = vault.initObserver(); }
  else if (v === 'discovery') { discovery.loadPage(); discoveryObs = discovery.initObserver(); }
  else if (v === 'feed') { feed.loadPage(); feedObs = feed.initObserver(); }

  if (window.innerWidth < 1024 && (v === 'history' || v === 'tasks')) toggleConsole('minimize');
}

const router = createRouter(state, setView, lightbox.openById);

// ── Console Toggle ─────────────────────────────
function toggleConsole(forceState) {
  const el = document.getElementById('desktopConsole');
  const stub = document.getElementById('mobileToggleStub');
  let isMin = el?.classList.contains('minimized');
  if (forceState === 'expand') isMin = false;
  else if (forceState === 'minimize') isMin = true;
  else isMin = !isMin;
  if (el) el.classList.toggle('minimized', isMin);
  const txt = document.getElementById('consoleToggleText');
  if (txt) txt.textContent = isMin ? 'Expand' : 'Minimize';
  if (stub) stub.style.display = isMin ? 'block' : 'none';
}

// ── Health Check ───────────────────────────────
async function checkBackend() {
  const el = document.getElementById('backendStatus');
  try { const res = await api.apiFetch('/health'); if (el) el.textContent = res.status === 'ok' ? 'Backend Online' : 'Backend Latency'; }
  catch { if (el) el.textContent = 'Backend Offline'; }
}

// ── Success Handler (bridges forge → vault) ────
function handleSuccess(urls, requestId, payload, meta) {
  state.set('app.activeRequestId', requestId);
  state.set('vault.loaded', false);
  vault.render();
}

// ── Expose Globals for HTML onclick (transitional) ──
window.Studio = {
  state, api, toast, forge, vault, discovery, feed, lightbox, auth,
  setView, toggleConsole, openConfirm, closeConfirm, checkBackend,
  // Direct action proxies
  runGeneration: () => forge.runGeneration(handleSuccess),
  runMatrixCast: () => forge.runMatrixCast(),
  rollOracle: forge.rollOracle,
  clearPrompt: forge.clearPrompt,
  pastePrompt: forge.pastePrompt,
  openHistoryGroup: lightbox.open,
  closeBubbleReveal: lightbox.close,
  cloneActiveManifestation: () => lightbox.cloneToForge(forge.applyMode),
  hideCurrentItem: () => lightbox.setImageVisibility(true),
  showCurrentItem: () => lightbox.setImageVisibility(false),
  banishCurrentItem: () => { openConfirm('Banish Spirit?', 'This manifestation will fade into the void.', lightbox.banishImage); },
  banishBatch: () => { openConfirm('Banish Batch?', 'Return all spirits to the void forever.', lightbox.banishBatch); },
  toggleBatchHidden: lightbox.toggleBatchHidden,
  togglePublishCurrentBatch: lightbox.togglePublish,
  shareCurrentImage: lightbox.shareImage,
  reloadHistory: vault.reload,
  reloadDiscovery: discovery.reload,
  reloadFeed: feed.reload,
  filterByRealm: vault.filterByRealm,
  toggleHiddenVault: vault.toggleHidden,
  toggleSelectionMode: vault.toggleSelectionMode,
  executeBulkAction: vault.executeBulkAction,
  logout: auth.logout,
  applyMode: forge.applyMode,
  cancelJob: async (id) => { try { await api.apiFetch(`/cancel-job/${id}`, { method: 'POST' }); toast('Job Cancellation Initiated.', 'info'); } catch (err) { toast('Cancellation Error.', 'error'); } },
  toggleMatrixPause: () => { state.set('matrix.paused', !state.get('matrix.paused')); },
  cancelMatrix: () => { state.set('matrix.cancelled', true); state.set('matrix.paused', false); },
  createPost: feed.createPost,
  copyRequestId: async (id) => { if (id) { await navigator.clipboard.writeText(id); toast('Copied ID.', 'info'); } },
};

// ── Global Function Aliases (for HTML onclick) ──
// These bridge old inline handlers to new modules
window.toggleConsole = toggleConsole;
window.closeBubbleReveal = lightbox.close;
window.cloneActiveManifestation = () => lightbox.cloneToForge(forge.applyMode);
window.hideCurrentItem = () => lightbox.setImageVisibility(true);
window.showCurrentItem = () => lightbox.setImageVisibility(false);
window.banishCurrentItem = () => openConfirm('Banish Spirit?', 'This manifestation will fade into the void.', lightbox.banishImage);
window.banishBatch = () => openConfirm('Banish Batch?', 'Return all spirits to the void forever.', lightbox.banishBatch);
window.toggleBatchHidden = lightbox.toggleBatchHidden;
window.togglePublishCurrentBatch = lightbox.togglePublish;
window.shareCurrentImage = lightbox.shareImage;
window.runGeneration = () => forge.runGeneration(handleSuccess);
window.runMatrixCast = () => forge.runMatrixCast();
window.rollOracle = forge.rollOracle;
window.clearPrompt = forge.clearPrompt;
window.pastePrompt = forge.pastePrompt;
window.reloadHistory = vault.reload;
window.reloadDiscovery = discovery.reload;
window.reloadFeed = feed.reload;
window.filterVaultByRealm = vault.filterByRealm;
window.toggleHiddenVault = vault.toggleHidden;
window.toggleSelectionMode = vault.toggleSelectionMode;
window.executeBulkAction = vault.executeBulkAction;
window.logout = auth.logout;
window.openHistoryGroup = lightbox.open;
window.loadHistoryPage = vault.loadPage;
window.loadDiscoveryPage = discovery.loadPage;
window.loadFeedPage = feed.loadPage;
window.createPost = feed.createPost;
window.toggleMatrixPause = () => { state.set('matrix.paused', !state.get('matrix.paused')); };
window.cancelMatrix = () => { state.set('matrix.cancelled', true); state.set('matrix.paused', false); };
window.cancelAllJobs = async () => { if (!confirm('Halt all active manifestations?')) return; try { await api.apiFetch('/cancel-all-jobs', { method: 'POST' }); toast('All Jobs Halted.', 'success'); } catch (err) { toast('Global Halt Error.', 'error'); } };
window.clearVault = () => { if (confirm('Clear local cache?')) { localStorage.removeItem('a_vault_cache'); const list = document.getElementById('historyList'); if (list) list.innerHTML = ''; vault.reload(); } };
window.copyRequestId = async (id) => { if (id) { await navigator.clipboard.writeText(id); toast('Copied ID.', 'info'); } };
window.cancelJob = async (id) => { try { await api.apiFetch(`/cancel-job/${id}`, { method: 'POST' }); toast('Job Cancellation Initiated.', 'info'); } catch (err) { toast('Cancellation Error.', 'error'); } };

// ── Tab Visibility ─────────────────────────────
document.addEventListener('visibilitychange', () => {
  state.set('app.isTabVisible', !document.hidden);
  if (!document.hidden) {
    const isVault = state.get('app.activeView') === 'history';
    if (isVault) vault.render();
  }
});

// ── Initialization ─────────────────────────────
try {
  forge.applyMode(state.get('app.mode') || 'standard');
  router.handleRouting();
  auth.checkAuth().then(loggedIn => { if (loggedIn) vault.reload(); });
  checkBackend();
  setInterval(checkBackend, 30000);
  initAetherCanvas(state);

  // Nav pills
  document.querySelectorAll('[data-view]').forEach(btn =>
    btn.addEventListener('click', (e) => setView(e.currentTarget.dataset.view)));

  // Mode toggles
  document.querySelectorAll('[data-mode]').forEach(btn =>
    btn.addEventListener('click', () => forge.applyMode(btn.dataset.mode)));

  // Generate button
  document.getElementById('generateBtn')?.addEventListener('click', () => forge.runGeneration(handleSuccess));

  // Matrix button
  document.getElementById('matrixBtn')?.addEventListener('click', () => forge.runMatrixCast());

  console.log('✨ Aether Studio initialized');
} catch (e) {
  console.error('Initialization error:', e);
  toast('Connect to Server for full functionality.', 'info');
}
