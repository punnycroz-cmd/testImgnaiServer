/* Aether Studio — Discovery View Module */

export function createDiscoveryView(state, api, toast, createBatchCard) {
  const dom = {
    list: () => document.getElementById('discoveryList'),
    loadMore: () => document.getElementById('loadMoreDiscoveryBtn'),
  };

  async function loadPage() {
    if (state.get('discovery.loading') || !state.get('discovery.hasMore')) return;
    state.set('discovery.loading', true);
    try {
      const cursor = state.get('discovery.cursor');
      const url = `/public-gallery?limit=20${cursor ? `&before=${cursor}` : ''}`;
      const res = await api.apiFetch(url);
      if (!res) return; // 304 Not Modified or empty
      
      const list = dom.list();
      if (!cursor) list.innerHTML = '';
      
      const items = res.items || [];
      items.forEach(item => {
        const card = createBatchCard(item);
        list.appendChild(card);
      });
      
      state.set('discovery.cursor', res.next_cursor);
      state.set('discovery.hasMore', res.has_more);
      const btn = dom.loadMore();
      if (btn) btn.classList.toggle('hidden', !res.has_more);
    } catch (err) {
      console.error('Discovery failed:', err);
    } finally {
      state.set('discovery.loading', false);
      const list = dom.list();
      if (list) { list.classList.remove('opacity-50', 'pointer-events-none'); }
    }
  }

  function reload() {
    state.set('discovery.loading', false);
    state.set('discovery.hasMore', true);
    state.set('discovery.cursor', null);
    const list = dom.list();
    if (list) list.classList.add('opacity-50', 'pointer-events-none');
    loadPage();
  }

  function initObserver() {
    const btn = dom.loadMore();
    if (!btn) return null;
    const obs = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && !state.get('discovery.loading') && state.get('discovery.hasMore')) {
        loadPage();
      }
    }, { root: document.querySelector('main'), rootMargin: '300px', threshold: 0.1 });
    obs.observe(btn);
    return obs;
  }

  return { loadPage, reload, initObserver };
}
