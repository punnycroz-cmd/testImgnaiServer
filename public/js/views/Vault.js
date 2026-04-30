/* Aether Studio — Vault View Module */
import { escapeHtml } from '../utils/dom.js';

export function createVaultView(state, api, toast, openHistoryGroup) {
  const dom = {
    list: () => document.getElementById('historyList'),
    loadMore: () => document.getElementById('loadMoreBtn'),
  };

  function createBatchCard(entry) {
    const wrap = document.createElement('div');
    wrap.id = `batch-${entry.request_id}`;
    wrap.dataset.realm = entry.realm || 'day';
    wrap.className = 'glass-panel p-4 pb-5 cursor-pointer group relative transition-all duration-500 hover:scale-[1.02] hover:shadow-[0_20px_50px_rgba(0,0,0,0.4)] border-white/5 hover:border-white/20';
    const selIds = state.get('vault.selectedIds');
    if (selIds && selIds.has(entry.request_id)) wrap.classList.add('border-[var(--accent)]', 'bg-[var(--accent)]/10');
    if (entry.is_hidden) wrap.classList.add('opacity-65');

    wrap.onclick = (e) => {
      if (e.target.closest('button')) return;
      if (state.get('vault.selectionMode')) { toggleBatchSelection(entry.request_id); }
      else { openHistoryGroup(entry); }
    };

    const selIds = state.get('vault.selectedIds');
    const isSelected = selIds && selIds.has(entry.request_id);
    const showHidden = state.get('vault.showHidden');

    wrap.innerHTML = `
      <div class="flex items-center justify-between gap-2 mb-3">
        <div class="min-w-0">
          <div class="flex items-center gap-2 mb-1">
            <div class="text-[9px] uppercase tracking-widest font-black px-2 py-0.5 rounded ${entry.realm === 'star' ? 'bg-purple-500/20 text-purple-400' : 'bg-emerald-500/20 text-emerald-600'}">${entry.realm || 'day'}</div>
            ${entry.is_hidden ? '<div class="text-[9px] font-black uppercase tracking-widest bg-red-500/15 text-red-400 px-1 rounded">Hidden</div>' : ''}
            <div class="public-badge ${entry.is_public ? '' : 'hidden'} text-[9px] font-black uppercase tracking-widest bg-violet-500/20 text-violet-400 px-1 rounded">Shared</div>
          </div>
          <div class="text-xs font-bold truncate opacity-80">${escapeHtml(entry.prompt || 'No Inscription')}</div>
        </div>
        <div class="selection-indicator ${state.get('vault.selectionMode') ? 'flex' : 'hidden'} w-5 h-5 rounded-full border-2 border-white/20 items-center justify-center ${isSelected ? 'bg-[var(--accent)] border-[var(--accent)]' : ''}">
          ${isSelected ? '<svg class="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20"><path d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"/></svg>' : ''}
        </div>
      </div>
      <div class="grid grid-cols-2 gap-2">
        ${(entry.images || []).slice(0, 4).map(img => {
          const isH = img.status === 'hidden';
          const isD = img.status === 'deleting';
          return `<div class="art-frame shimmer relative group/card ${isH ? 'ring-1 ring-red-400/60' : ''} ${isD ? 'spirit-deleting' : ''} ${isH && !showHidden ? 'hidden-collapsed' : ''}">
            <img src="${img.thumbnail_url || img.r2_url}" class="w-full aspect-square object-cover relative z-10 opacity-0 transition-all duration-700 scale-105 group-hover/card:scale-110 ${isH ? 'spirit-hidden' : ''}" loading="lazy"
              onload="this.style.opacity=('${isH}'==='true'?'0.75':'1');this.style.transform='scale(1)';this.parentElement.classList.remove('shimmer');">
          </div>`;
        }).join('')}
      </div>`;
    return wrap;
  }

  function toggleBatchSelection(id) {
    const sel = state.get('vault.selectedIds') || new Set();
    if (sel.has(id)) sel.delete(id); else sel.add(id);
    state.set('vault.selectedIds', sel);
    const el = document.getElementById(`batch-${id}`);
    if (el) {
      const isSel = sel.has(id);
      el.classList.toggle('border-[var(--accent)]', isSel);
      const ind = el.querySelector('.selection-indicator');
      if (ind) {
        ind.classList.toggle('bg-[var(--accent)]', isSel);
        ind.classList.toggle('border-[var(--accent)]', isSel);
        ind.innerHTML = isSel ? '<svg class="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20"><path d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"/></svg>' : '';
      }
    }
    updateSelectionUI();
  }

  function updateSelectionUI() {
    const bar = document.getElementById('selectionBar');
    const countEl = document.getElementById('selectCount');
    const total = (state.get('vault.selectedIds') || new Set()).size;
    if (countEl) countEl.textContent = total;
    if (bar) { if (total > 0 && state.get('vault.selectionMode')) bar.classList.remove('hidden'); else bar.classList.add('hidden'); }
  }

  function toggleSelectionMode(forceValue) {
    const next = forceValue !== undefined ? forceValue : !state.get('vault.selectionMode');
    state.set('vault.selectionMode', next);
    if (!next) state.set('vault.selectedIds', new Set());
    const btn = document.getElementById('toggleSelectBtn');
    if (btn) btn.textContent = next ? 'Cancel' : 'Select Mode';
    document.querySelectorAll('#historyList > div').forEach(card => {
      const ind = card.querySelector('.selection-indicator');
      if (ind) { ind.classList.toggle('hidden', !next); ind.classList.toggle('flex', next); }
      if (!next) { card.classList.remove('border-[var(--accent)]'); if (ind) { ind.classList.remove('bg-[var(--accent)]'); ind.innerHTML = ''; } }
    });
    updateSelectionUI();
  }

  function filterByRealm(realm) {
    state.set('vault.realmFilter', realm);
    ['all', 'day', 'star'].forEach(r => {
      const btn = document.getElementById(`filterRealm${r.charAt(0).toUpperCase() + r.slice(1)}`);
      if (!btn) return;
      if (r === realm) { btn.classList.remove('opacity-50'); btn.classList.add('bg-[var(--accent)]', 'text-white', 'shadow-sm'); }
      else { btn.classList.add('opacity-50'); btn.classList.remove('bg-[var(--accent)]', 'text-white', 'shadow-sm'); }
    });
    document.querySelectorAll('#historyList > div[id^="batch-"]').forEach(card => {
      const cr = card.dataset.realm || 'day';
      if (realm === 'all' || cr === realm) { card.style.display = ''; card.style.opacity = '1'; }
      else { card.style.opacity = '0'; setTimeout(() => { if (card.style.opacity === '0') card.style.display = 'none'; }, 300); }
    });
  }

  function toggleHidden() {
    const next = !state.get('vault.showHidden');
    state.set('vault.showHidden', next);
    const btn = document.getElementById('toggleHiddenVaultBtn');
    if (btn) { btn.classList.toggle('text-[var(--accent)]', next); btn.classList.toggle('opacity-60', !next); btn.textContent = next ? 'Hide Hidden' : 'Show Hidden'; }
    reload();
  }

  async function loadPage() {
    if (state.get('vault.loading') || !state.get('vault.hasMore')) return;
    state.set('vault.loading', true);
    const btn = dom.loadMore();
    if (btn) btn.textContent = 'Summoning...';
    try {
      const cursor = state.get('vault.cursor');
      const uid = state.get('auth.uid');
      const showHidden = state.get('vault.showHidden');
      const url = `/history?limit=20${cursor ? `&before=${cursor}` : ''}&uid=${uid}&include_hidden=${showHidden}&_t=${Date.now()}`;
      const res = await api.apiFetch(url);
      if (!res) return;
      const items = res.items || [];
      const list = dom.list();
      const pending = state.get('forge.pendingDeletions') || new Set();
      const filter = state.get('vault.realmFilter');

      for (const entry of items) {
        if (pending.has(entry.request_id)) continue;
        if (!entry.images || entry.images.length === 0) continue;
        if (document.getElementById(`batch-${entry.request_id}`)) continue;
        const card = createBatchCard(entry);
        const matches = filter === 'all' || (entry.realm || 'day') === filter;
        if (!matches) { card.style.display = 'none'; }
        else { card.style.opacity = '0'; card.style.transform = 'translateY(10px)'; }
        list.appendChild(card);
        if (matches) {
          requestAnimationFrame(() => { card.style.transition = 'all 0.6s ease'; card.style.opacity = '1'; card.style.transform = 'translateY(0)'; });
        }
      }

      if (items.length > 0) state.set('vault.cursor', items[items.length - 1].image_id_seq);
      state.set('vault.hasMore', !!res.has_more);
    } catch (err) { console.error('Vault load error:', err); }
    finally { state.set('vault.loading', false); }

    // Update load more button
    const loadBtn = dom.loadMore();
    const listEl = dom.list();
    const total = (listEl && listEl.children) ? listEl.children.length : 0;
    if (loadBtn) {
      if (!state.get('vault.hasMore')) { loadBtn.classList.remove('hidden'); loadBtn.disabled = true; loadBtn.textContent = `End of Vault (${total} Total)`; loadBtn.style.opacity = '0.5'; }
      else { loadBtn.classList.remove('hidden'); loadBtn.disabled = false; loadBtn.style.opacity = '1'; loadBtn.textContent = `Load More (${total} shown)`; }
    }
  }

  async function render(reset = false) {
    const list = dom.list();
    if (!list || document.getElementById('view-history').classList.contains('hidden')) return;
    if (state.get('vault.loaded') && !reset && list.innerHTML !== '') return;
    state.set('vault.loaded', true);
    state.set('vault.cursor', null);
    state.set('vault.hasMore', true);
    list.innerHTML = '';
    list.classList.remove('opacity-50', 'pointer-events-none');
    await loadPage();
  }

  function reload() {
    state.set('vault.loaded', false);
    state.set('vault.cursor', null);
    const list = dom.list();
    if (list) list.classList.add('opacity-50', 'pointer-events-none');
    render();
  }

  async function executeBulkAction(action) {
    const ids = Array.from(state.get('vault.selectedIds') || []);
    if (!ids.length) return;
    if (action === 'delete') {
      ids.forEach(id => { const el = document.getElementById(`batch-${id}`); if (el) { el.style.filter = 'grayscale(1) blur(40px)'; el.style.opacity = '0'; } });
      for (const id of ids) { api.apiFetch(`/history/batch/${id}`, { method: 'DELETE' }).catch(() => {}); }
      toast(`Banishing ${ids.length} manifestations...`, 'info');
      setTimeout(() => { ids.forEach(id => { const el = document.getElementById(`batch-${id}`); if (el) el.remove(); }); toggleSelectionMode(false); }, 850);
    } else if (action === 'hide') {
      ids.forEach(id => { const el = document.getElementById(`batch-${id}`); if (el) { el.style.filter = 'blur(20px)'; el.style.opacity = '0'; } });
      for (const id of ids) { api.apiFetch(`/history/batch/${id}/hide`, { method: 'POST' }).catch(() => {}); }
      toast(`Hiding ${ids.length} manifestations...`, 'info');
      setTimeout(() => { ids.forEach(id => { const el = document.getElementById(`batch-${id}`); if (el) el.remove(); }); toggleSelectionMode(false); }, 650);
    }
  }

  function initObserver() {
    const btn = dom.loadMore();
    if (!btn) return null;
    const obs = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && !state.get('vault.loading') && state.get('vault.hasMore')) loadPage();
    }, { root: document.querySelector('main'), rootMargin: '300px', threshold: 0.1 });
    obs.observe(btn);
    return obs;
  }

  return { createBatchCard, loadPage, render, reload, filterByRealm, toggleHidden, toggleSelectionMode, toggleBatchSelection, executeBulkAction, updateSelectionUI, initObserver };
}
