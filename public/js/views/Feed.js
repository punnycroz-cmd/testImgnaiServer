/* Aether Studio — Feed View Module */
import { escapeHtml } from '../utils/dom.js';

export function createFeedView(state, api, toast) {
  const dom = {
    list: () => document.getElementById('feedList'),
    loadMore: () => document.getElementById('loadMoreFeedBtn'),
    postContent: () => document.getElementById('feed-post-content'),
  };

  function createPostCard(post) {
    const div = document.createElement('div');
    div.className = 'panel-obsidian p-6 lg:p-8 w-full border border-gold-400/20 mb-6 relative group transition-all hover:-translate-y-1 hover:shadow-2xl';
    div.innerHTML = `
      <div class="flex items-center gap-4 mb-5">
        <img class="w-10 h-10 rounded border border-gold-400/50 bg-obsidian-900 shadow-glow-gold" src="${post.picture || 'https://api.dicebear.com/7.x/avataaars/svg?seed='+post.name+'&backgroundColor=141414'}" alt="">
        <div>
          <p class="text-sm font-bold text-gold-400 tracking-wide uppercase">${post.name || 'Unknown Mage'}</p>
          <p class="text-[10px] text-white/40 uppercase tracking-[0.2em] font-semibold mt-0.5">${new Date(post.created_at).toLocaleString()}</p>
        </div>
      </div>
      <p class="text-[15px] font-medium text-cinematic text-white mb-5 leading-relaxed italic">"${escapeHtml(post.content)}"</p>
      ${post.preview_url ? `
        <div class="art-frame overflow-hidden border border-gold-400/20 mb-6 cursor-pointer shadow-lg group-hover:border-gold-400/50 transition-colors" onclick="window.Studio.vault.openById('${post.request_id}')">
          <img class="w-full object-cover hover:scale-105 transition-transform duration-1000" src="${post.preview_url}" alt="">
        </div>
      ` : ''}
      <div class="flex gap-6 border-t border-gold-400/10 pt-4">
        <button class="text-[11px] uppercase tracking-[0.2em] font-bold text-white/40 hover:text-gold-400 transition-colors flex items-center gap-2"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg> Like</button>
      </div>`;
    return div;
  }

  async function loadPage() {
    if (state.get('feed.loading') || !state.get('feed.hasMore')) return;
    state.set('feed.loading', true);
    try {
      const cursor = state.get('feed.cursor');
      const url = `/posts?limit=20${cursor ? `&before=${cursor}` : ''}`;
      const res = await api.apiFetch(url);
      if (!res) return; // 304 Not Modified or empty
      
      const list = dom.list();
      if (!cursor) list.innerHTML = '';
      
      const items = res.items || [];
      items.forEach(post => list.appendChild(createPostCard(post)));
      
      state.set('feed.cursor', res.next_cursor);
      state.set('feed.hasMore', res.has_more);
      const btn = dom.loadMore();
      if (btn) btn.classList.toggle('hidden', !res.has_more);
    } catch (err) { console.error('Feed failed:', err); }
    finally {
      state.set('feed.loading', false);
      const list = dom.list();
      if (list) list.classList.remove('opacity-50', 'pointer-events-none');
    }
  }

  function reload() {
    state.set('feed.loading', false);
    state.set('feed.hasMore', true);
    state.set('feed.cursor', null);
    const list = dom.list();
    if (list) list.classList.add('opacity-50', 'pointer-events-none');
    loadPage();
  }

  async function createPost() {
    const el = dom.postContent();
    const content = (el && el.value) ? el.value.trim() : '';
    if (!content) return;
    try {
      await api.apiFetch('/posts', { method: 'POST', body: JSON.stringify({ content }) });
      el.value = '';
      reload();
      toast('Status broadcasted!', 'info');
    } catch (err) { toast('Failed to broadcast status.', 'error'); }
  }

  function initObserver() {
    const btn = dom.loadMore();
    if (!btn) return null;
    const obs = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && !state.get('feed.loading') && state.get('feed.hasMore')) loadPage();
    }, { root: document.getElementById('mainScrollArea'), rootMargin: '300px', threshold: 0.1 });
    obs.observe(btn);
    return obs;
  }

  return { loadPage, reload, createPost, initObserver };
}
