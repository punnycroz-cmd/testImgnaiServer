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
    div.className = 'hud-panel p-6 flex gap-4';
    div.innerHTML = `
      <img class="w-12 h-12 object-cover border border-accent" src="${post.picture || ''}" alt="" style="clip-path: var(--clip-corner-sm)">
      <div class="flex-1 min-w-0">
        <div class="flex items-center justify-between mb-1">
          <span class="hud-data text-accent">${post.name || 'UNKNOWN.OP'}</span>
          <span class="font-data text-[10px] text-[var(--text-muted)]">${new Date(post.created_at).toLocaleString()}</span>
        </div>
        <p class="text-[14px] text-white font-medium leading-relaxed whitespace-pre-wrap mb-4">${escapeHtml(post.content)}</p>
        ${post.preview_url ? `
          <div class="relative group/feed-img cursor-pointer max-w-sm" onclick="window.Studio.vault.openById('${post.request_id}')">
            <img class="border border-[var(--hud-border)] transition-transform group-hover/feed-img:scale-[1.02]" style="clip-path: var(--clip-corner)" src="${post.preview_url}" alt="">
            <div class="absolute inset-0 bg-black/50 group-hover/feed-img:bg-transparent transition-all flex items-center justify-center" style="clip-path: var(--clip-corner)">
               <span class="bg-black/80 border border-accent text-accent px-4 py-2 text-[10px] font-black tracking-widest uppercase opacity-0 group-hover/feed-img:opacity-100 transition-opacity">ENGAGE.INSPECT</span>
            </div>
          </div>
        ` : ''}
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
    }, { root: document.querySelector('main'), rootMargin: '300px', threshold: 0.1 });
    obs.observe(btn);
    return obs;
  }

  return { loadPage, reload, createPost, initObserver };
}
