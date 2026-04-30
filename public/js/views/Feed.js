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
    div.className = 'glass-panel p-6 flex gap-4 border-white/5 hover:border-[var(--accent)]/20 transition-all';
    div.innerHTML = `
      <img class="w-10 h-10 rounded-xl object-cover border border-white/10" src="${post.picture || ''}" alt="">
      <div class="flex-1 min-w-0">
        <div class="flex items-center justify-between mb-1">
          <span class="font-black text-[10px] uppercase tracking-widest text-[var(--accent)]">${post.name || 'Unknown'}</span>
          <span class="text-[9px] opacity-40 uppercase font-bold">${new Date(post.created_at).toLocaleString()}</span>
        </div>
        <p class="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">${escapeHtml(post.content)}</p>
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
      const list = dom.list();
      if (!cursor) list.innerHTML = '';
      res.items.forEach(post => list.appendChild(createPostCard(post)));
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
    const content = el?.value?.trim();
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
    }, { root: document.querySelector('main'), rootMargin: '300px', threshold: 0.1 });
    obs.observe(btn);
    return obs;
  }

  return { loadPage, reload, createPost, initObserver };
}
