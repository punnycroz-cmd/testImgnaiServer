/* Aether Studio — Lightbox Module */
import { canonicalImageUrl } from '../utils/dom.js';

export function createLightbox(state, api, toast) {
  const el = {
    reveal: () => document.getElementById('bubbleReveal'),
    img: () => document.getElementById('bubbleRevealImg'),
    download: () => document.getElementById('bubbleRevealDownload'),
    thumbsSection: () => document.getElementById('thumbsSection'),
    thumbsGrid: () => document.getElementById('bubbleRevealThumbs'),
    metaModel: () => document.getElementById('metaModel'),
    metaRealm: () => document.getElementById('metaRealm'),
    metaPrompt: () => document.getElementById('metaPrompt'),
    bubbleMeta: () => document.getElementById('bubbleMeta'),
    publishBtn: () => document.getElementById('publishBtn'),
  };

  function populateInspector(data) {
    const model = el.metaModel(), realm = el.metaRealm(), prompt = el.metaPrompt();
    if (!data?.prompt) return;
    if (realm) realm.textContent = data.realm || 'day';
    if (model) model.textContent = data.model || 'Standard';
    if (prompt) prompt.textContent = data.prompt;
  }

  function open(entry, focusUrl = null) {
    if (!entry) return;
    state.set('lightbox.data', entry);
    const images = entry.images || [];
    const activeImages = images.filter(i => i.status !== 'deleting');
    const urls = activeImages.map(img => img.r2_url);
    if (!urls.length && !images.some(i => i.status === 'deleting')) return;
    const targetUrl = focusUrl || urls[0] || images[0]?.r2_url;
    const targetObj = images.find(i => i.r2_url === targetUrl) || images[0];
    const isHidden = targetObj?.status === 'hidden';
    const img = el.img();
    if (img) { img.src = targetUrl; img.dataset.hidden = isHidden ? 'true' : 'false'; img.classList.toggle('spirit-hidden', isHidden && state.get('vault.showHidden')); img.classList.toggle('spirit-deleting', targetObj?.status === 'deleting'); }
    const dl = el.download();
    if (dl) dl.href = targetUrl;
    const meta = el.bubbleMeta();
    if (meta) meta.textContent = `#${(targetObj?.image_index ?? 0) + 1}`;
    state.set('lightbox.currentUrl', targetUrl);
    state.set('lightbox.currentIndex', targetObj?.image_index ?? 0);
    state.set('lightbox.currentHidden', isHidden);
    populateInspector(entry);
    updatePublishButton();

    // Thumbnails
    const ts = el.thumbsSection(), tg = el.thumbsGrid();
    if (images.length > 1 && ts && tg) {
      ts.style.display = 'flex';
      tg.innerHTML = images.map(imgData => {
        const isH = imgData.status === 'hidden';
        const isD = imgData.status === 'deleting';
        const isT = imgData.r2_url === targetUrl;
        const showHidden = state.get('vault.showHidden');
        return `<button class="art-frame overflow-hidden border-2 transition-all ${isT ? 'border-[var(--accent)]' : 'border-transparent'} ${isH ? 'ring-1 ring-red-400/60' : ''} ${isD ? 'spirit-deleting' : ''} ${isH && !showHidden ? 'hidden-collapsed' : ''}" data-thumb-url="${imgData.r2_url}">
          <img src="${imgData.r2_url}" class="w-full aspect-square object-cover ${isH ? 'spirit-hidden' : ''}" loading="lazy">
        </button>`;
      }).join('');
      // Delegate thumb clicks
      tg.querySelectorAll('[data-thumb-url]').forEach(btn => {
        btn.addEventListener('click', (e) => { e.stopPropagation(); open(state.get('lightbox.data'), btn.dataset.thumbUrl); });
      });
    } else if (ts) { ts.style.display = 'none'; }

    const reveal = el.reveal();
    if (reveal && !reveal.classList.contains('active')) {
      reveal.style.display = 'flex';
      setTimeout(() => reveal.classList.add('active'), 10);
    }
  }

  function close(e) {
    if (e?.target?.tagName === 'IMG') return;
    const reveal = el.reveal();
    if (reveal) { reveal.classList.remove('active'); setTimeout(() => { reveal.style.display = 'none'; state.set('lightbox.data', null); state.set('lightbox.currentUrl', null); }, 350); }
  }

  async function openById(rid) {
    try {
      const entry = await api.apiFetch(`/history?request_id=${rid}`);
      if (entry) open(entry);
    } catch (err) { toast('Could not load manifestation details.', 'error'); }
  }

  function cloneToForge(applyMode) {
    const data = state.get('lightbox.data');
    if (!data) return;
    if (data.realm) applyMode(data.realm === 'star' ? 'nsfw' : 'standard');
    const setVal = (id, val) => { const el = document.getElementById(id); if (el && val) el.value = val; };
    setVal('model', data.model);
    setVal('prompt', data.prompt);
    setVal('negativePrompt', data.negative_prompt);
    setVal('aspect', data.aspect);
    setVal('quality', data.quality);
    setVal('seed', data.seed);
    close();
    toast('Visions cloned to Forge.', 'info');
  }

  async function setImageVisibility(hidden) {
    const data = state.get('lightbox.data');
    const requestId = data?.request_id;
    const index = state.get('lightbox.currentIndex');
    if (!requestId || index === undefined) return toast('Cannot toggle visibility.', 'error');
    const endpoint = hidden ? 'hide' : 'show';
    try {
      await api.apiFetch(`/history/image/${encodeURIComponent(requestId)}/${endpoint}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ index: parseInt(index, 10) }) });
      if (data.images?.[index]) data.images[index].status = hidden ? 'hidden' : 'active';
      if (hidden && !state.get('vault.showHidden')) {
        const remaining = data.images.filter(i => i.status !== 'hidden' && i.status !== 'deleting');
        if (remaining.length > 0) { open(data, (remaining.find(i => i.image_index > index) || remaining[0]).r2_url); }
        else close();
      } else { open(data, state.get('lightbox.currentUrl')); }
      toast(hidden ? 'Spirit hidden.' : 'Spirit restored.', 'info');
    } catch (err) { toast('Visibility change failed.', 'error'); }
  }

  async function toggleBatchHidden() {
    const data = state.get('lightbox.data');
    if (!data?.request_id) return;
    const hasVisible = (data.images || []).some(img => img.status !== 'hidden' && img.status !== 'deleting');
    const endpoint = hasVisible ? 'hide' : 'show';
    try {
      await api.apiFetch(`/history/batch/${encodeURIComponent(data.request_id)}/${endpoint}`, { method: 'POST' });
      data.is_hidden = hasVisible;
      if (data.images) data.images.forEach(img => { if (img.status !== 'deleting') img.status = hasVisible ? 'hidden' : 'active'; });
      toast(hasVisible ? 'Batch hidden.' : 'Batch restored.', 'info');
    } catch (err) { toast('Batch visibility failed.', 'error'); }
  }

  async function banishImage() {
    const data = state.get('lightbox.data');
    const currentUrl = canonicalImageUrl(state.get('lightbox.currentUrl'));
    if (!data?.images) return;
    const imgObj = data.images.find(i => canonicalImageUrl(i.r2_url) === currentUrl);
    if (!imgObj) return;
    const img = el.img();
    if (img) img.classList.add('spirit-deleting');
    imgObj.status = 'deleting';
    try {
      await api.apiFetch(`/history/image/${encodeURIComponent(data.request_id)}?url=${encodeURIComponent(currentUrl)}`, { method: 'DELETE', body: JSON.stringify({ url: currentUrl }) });
      const remaining = data.images.filter(i => i.status === 'active' || i.status === 'hidden');
      setTimeout(() => { if (remaining.length > 0) { open(data, (remaining.find(i => (i.image_index || 0) > (imgObj.image_index || 0)) || remaining[0]).r2_url); } else close(); }, 1200);
    } catch (e) { toast('Banishment fractured.', 'error'); if (img) img.classList.remove('spirit-deleting'); }
  }

  async function banishBatch() {
    const data = state.get('lightbox.data');
    if (!data?.request_id) return;
    try {
      await api.apiFetch(`/history/batch/${encodeURIComponent(data.request_id)}`, { method: 'DELETE' });
      toast('Manifestation dissolved.', 'info');
      const card = document.getElementById(`batch-${data.request_id}`);
      if (card) card.remove();
      close();
    } catch (e) { toast('Dissolution failed.', 'error'); }
  }

  async function togglePublish() {
    const data = state.get('lightbox.data');
    if (!data?.request_id) return;
    const next = !data.is_public;
    try {
      await api.apiFetch(`/history/batch/${data.request_id}/public`, { method: 'POST', body: JSON.stringify({ is_public: next }) });
      data.is_public = next;
      updatePublishButton();
      toast(next ? 'Batch published!' : 'Batch removed from gallery.', 'info');
      const card = document.getElementById(`batch-${data.request_id}`);
      if (card) { const badge = card.querySelector('.public-badge'); if (badge) badge.classList.toggle('hidden', !next); }
    } catch (err) { toast('Failed to update public status.', 'error'); }
  }

  function updatePublishButton() {
    const btn = el.publishBtn();
    const data = state.get('lightbox.data');
    if (!btn || !data) return;
    const isPublic = data.is_public || false;
    btn.textContent = isPublic ? 'Shared in Public' : 'Post to Public';
    btn.classList.toggle('bg-violet-600/40', isPublic);
    btn.classList.toggle('text-white', isPublic);
  }

  async function shareImage() {
    const data = state.get('lightbox.data');
    const currentUrl = state.get('lightbox.currentUrl');
    if (!data || !currentUrl) return;
    const idx = data.images.findIndex(i => i.r2_url === currentUrl || i.thumbnail_url === currentUrl);
    if (idx === -1) return toast('Unable to identify current image.', 'error');
    try {
      const res = await api.apiFetch('/api/share', { method: 'POST', body: JSON.stringify({ request_id: data.request_id, image_index: idx, title: data.prompt?.substring(0, 100) || 'AI Manifestation' }) });
      if (res.share_url) { await navigator.clipboard.writeText(res.share_url); toast('🔗 Public share link copied!', 'success'); }
    } catch (err) { toast('Sharing failed.', 'error'); }
  }

  return { open, close, openById, cloneToForge, setImageVisibility, toggleBatchHidden, banishImage, banishBatch, togglePublish, shareImage, populateInspector };
}
