/* Aether Studio — Forge View Module (Generation + Matrix) */
import { sleep, backoffDelay, resolveServerUrl } from '../utils/helpers.js';
import { DAY_MODELS, STAR_MODELS, ASPECT_CHOICES, QUALITY_CHOICES, ORACLE_PROMPTS } from '../constants.js';

export function createForgeView(state, api, toast) {
  const dom = {
    model: () => document.getElementById('model'),
    prompt: () => document.getElementById('prompt'),
    negativePrompt: () => document.getElementById('negativePrompt'),
    generateBtn: () => document.getElementById('generateBtn'),
    btnText: () => document.getElementById('btnText'),
    btnLoader: () => document.getElementById('btnLoader'),
    gallery: () => document.getElementById('gallery'),
    count: () => document.getElementById('count'),
    aspect: () => document.getElementById('aspect'),
    quality: () => document.getElementById('quality'),
    seed: () => document.getElementById('seed'),
    matrixBtn: () => document.getElementById('matrixBtn'),
    btnMatrixText: () => document.getElementById('btnMatrixText'),
    btnMatrixLoader: () => document.getElementById('btnMatrixLoader'),
  };

  function getPayload() {
    const realm = state.get('app.mode') === 'nsfw' ? 'star' : 'day';
    return {
      prompt: dom.prompt()?.value?.trim() || '',
      model: dom.model()?.value || '',
      nsfw: state.get('app.mode') === 'nsfw',
      count: parseInt(dom.count()?.value || '4', 10),
      aspect: dom.aspect()?.value || '1:1',
      quality: dom.quality()?.value || 'Fast',
      negative_prompt: dom.negativePrompt()?.value?.trim() || '',
      seed: dom.seed()?.value ? parseInt(dom.seed().value, 10) : null,
      client_id: `client-${Date.now()}`,
      realm,
    };
  }

  function setLoading(loading) {
    const btn = dom.generateBtn();
    if (btn) { btn.disabled = loading; btn.classList.toggle('opacity-50', loading); }
    const txt = dom.btnText();
    if (txt) txt.textContent = loading ? 'Weaving...' : 'Manifest';
    const ldr = dom.btnLoader();
    if (ldr) ldr.classList.toggle('hidden', !loading);
  }

  function applyMode(mode) {
    state.set('app.mode', mode);
    document.body.dataset.mode = mode;
    state.set('app.serverUrl', resolveServerUrl(mode));
    const m = dom.model(), q = dom.quality(), a = dom.aspect();
    const prevModel = m?.value || localStorage.getItem('a_model') || '';
    const models = mode === 'nsfw' ? STAR_MODELS : DAY_MODELS;
    if (m) m.innerHTML = models.map(n => `<option value="${n}">${n}</option>`).join('');
    if (q) q.innerHTML = QUALITY_CHOICES.map(v => `<option value="${v}">${v}</option>`).join('');
    if (a) a.innerHTML = ASPECT_CHOICES.map(v => `<option value="${v}">${v}</option>`).join('');
    if (m) m.value = models.includes(prevModel) ? prevModel : models[0];
    document.querySelectorAll('[data-mode]').forEach(btn => btn.classList.toggle('active', btn.dataset.mode === mode));
    localStorage.setItem('a_mode', mode);
    if (m) localStorage.setItem('a_model', m.value);
    const accent = mode === 'nsfw' ? '#8b5cf6' : '#10b981';
    document.documentElement.style.setProperty('--accent', accent);
  }

  function renderGallery(urls_or_imgs, requestId, payload, meta = {}) {
    const gallery = dom.gallery();
    if (!gallery) return;
    const normalized = urls_or_imgs.map(u => typeof u === 'string' ? { r2_url: u, status: 'active' } : (u.status ? u : { ...u, status: 'active' }));
    const pending = state.get('forge.pendingDeletions') || new Set();
    const visible = normalized.filter(img => !pending.has(img.r2_url?.split('?')[0]));
    if (!visible.length) { gallery.innerHTML = '<div class="col-span-full py-24 cinematic-text text-xl opacity-20 uppercase tracking-widest text-center">Manifestation Dissolved</div>'; return; }
    gallery.innerHTML = visible.map((img, idx) => `
      <div class="bubble ${img.status === 'deleting' ? 'spirit-deleting' : ''}" id="bubble-${requestId}-${idx}">
        ${(img.r2_url.includes('.r2.dev') || img.r2_url.includes('cloudflare')) ? '<span class="vault-badge">Vaulted</span>' : ''}
        <div class="bubble-img-overlay"><img src="${img.r2_url}" alt="Image ${idx + 1}" loading="lazy"></div>
        <div class="bubble-sphere"></div>
        <canvas class="bubble-canvas" width="260" height="260"></canvas>
      </div>`).join('');
    return visible;
  }

  async function pollUntilDone(requestId, payload, maxAttempts = 120) {
    state.set('app.currentPoll', requestId);
    const isStar = (payload?.realm || 'day') === 'star';
    const initialWait = isStar ? 40000 : 60000;
    toast(`Manifesting spirit... focus for ${Math.round(initialWait / 1000)}s.`, 'info');
    await sleep(initialWait);
    if (state.get('app.currentPoll') !== requestId) return false;

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      if (state.get('app.currentPoll') !== requestId) return false;
      try {
        const res = await api.apiFetch(`/job-status/${requestId}`);
        if (state.get('app.currentPoll') !== requestId) return false;
        if (res?.images?.length) {
          const urls = res.images.map(img => img.r2_url);
          const gallery = dom.gallery();
          if (gallery && urls.length > gallery.querySelectorAll('.bubble').length) renderGallery(urls, requestId, payload, res);
        }
        if (res?.status === 'done') {
          const finalUrls = res.images?.length ? res.images.map(i => i.r2_url) : res.result?.image_urls;
          if (finalUrls) { return { urls: finalUrls, meta: res }; }
        }
        if (res?.status === 'error' || res?.status === 'failed') { toast(res.error || 'Generation failed.', 'error'); return false; }
      } catch (err) { /* retry */ }
      await sleep(backoffDelay(attempt, isStar));
    }
    return false;
  }

  async function runGeneration(onSuccess) {
    const payload = getPayload();
    if (!payload.prompt) return toast('Inspiration required.', 'error');
    setLoading(true);
    state.set('app.isGenerating', true);
    const gallery = dom.gallery();
    if (gallery) { gallery.style.display = ''; gallery.innerHTML = '<div class="col-span-full py-24 animate-pulse opacity-50 cinematic-text text-2xl uppercase tracking-widest text-center">Weaving Vision...</div>'; }
    try {
      const res = await api.apiFetch('/generate', { method: 'POST', body: JSON.stringify(payload) });
      state.set('app.activeRequestId', res.request_id);
      if (res.status === 'done' && res.result?.image_urls?.length) {
        renderGallery(res.result.image_urls, res.request_id, payload, res);
        if (onSuccess) onSuccess(res.result.image_urls, res.request_id, payload, res);
        return;
      }
      toast(`Request accepted: ${res.request_id.slice(0, 8)}...`, 'info');
      const result = await pollUntilDone(res.request_id, payload);
      if (result) {
        renderGallery(result.urls, res.request_id, payload, result.meta);
        if (onSuccess) onSuccess(result.urls, res.request_id, payload, result.meta);
      }
    } catch (err) { toast(`Generation failed: ${err.message}`, 'error'); }
    finally { setLoading(false); state.set('app.isGenerating', false); }
  }

  async function runMatrixCast(onCellDone) {
    const payload = getPayload();
    if (!payload.prompt) return toast('Inspiration required.', 'error');
    const models = state.get('app.mode') === 'nsfw' ? STAR_MODELS : DAY_MODELS;
    const gallery = dom.gallery();
    if (gallery) gallery.style.display = 'none';
    const mGallery = document.getElementById('matrixGallery');
    if (mGallery) { mGallery.classList.remove('hidden'); mGallery.classList.add('grid'); mGallery.innerHTML = models.map(m => `
      <div id="matrix-cell-${m.replace(/\s+/g, '-')}" class="art-frame aspect-square flex flex-col items-center justify-center bg-black/40 border border-white/10 relative group overflow-hidden" data-realm="${payload.realm}">
        <span class="text-[10px] font-bold uppercase text-[var(--text-muted)] tracking-widest absolute bottom-3 z-20 bg-black/50 px-2 py-0.5 rounded-lg border border-white/5">${m}</span>
        <div class="loader opacity-40 hidden z-20" style="width:20px;height:20px;"></div>
        <img src="" class="absolute inset-0 w-full h-full object-cover hidden transition-all duration-1000 opacity-0 scale-110 z-10">
      </div>`).join(''); }
    const genBtn = dom.generateBtn();
    const matBtn = dom.matrixBtn();
    if (genBtn) genBtn.disabled = true;
    if (matBtn) matBtn.disabled = true;
    const mtxt = dom.btnMatrixText();
    const mldr = dom.btnMatrixLoader();
    if (mtxt) mtxt.textContent = 'Casting...';
    if (mldr) mldr.classList.remove('hidden');
    document.getElementById('matrixControls')?.classList.remove('hidden');
    state.set('matrix.paused', false);
    state.set('matrix.cancelled', false);
    const isStar = state.get('app.mode') === 'nsfw';
    const delay = isStar ? 40000 : 13000;
    let completed = 0;
    const statusText = document.getElementById('matrixStatusText');

    for (let i = 0; i < models.length; i++) {
      if (state.get('matrix.cancelled')) break;
      while (state.get('matrix.paused')) { await sleep(1000); if (state.get('matrix.cancelled')) break; }
      const model = models[i];
      const cell = document.getElementById(`matrix-cell-${model.replace(/\s+/g, '-')}`);
      if (cell) cell.querySelector('.loader')?.classList.remove('hidden');
      try {
        const res = await api.apiFetch('/generate', { method: 'POST', body: JSON.stringify({ ...payload, model }) });
        if (cell) cell.dataset.requestId = res.request_id;
        pollMatrixCell(res.request_id, cell, isStar).then(() => { completed++; if (statusText) statusText.textContent = `Manifesting: ${completed} / ${models.length} complete`; });
      } catch (e) { completed++; if (cell) cell.querySelector('.loader')?.classList.add('hidden'); }
      await sleep(delay);
    }
    while (completed < models.length && !state.get('matrix.cancelled')) await sleep(2000);
    toast('Celestial Matrix Complete.', 'success');
    if (genBtn) genBtn.disabled = false;
    if (matBtn) matBtn.disabled = false;
    if (mtxt) mtxt.textContent = 'Matrix';
    if (mldr) mldr.classList.add('hidden');
  }

  async function pollMatrixCell(requestId, cell, isStar) {
    const pollDelay = isStar ? 40000 : 3000;
    while (!state.get('matrix.cancelled')) {
      while (state.get('matrix.paused') && !state.get('matrix.cancelled')) await sleep(1000);
      if (state.get('matrix.cancelled')) break;
      try {
        const res = await api.apiFetch(`/job-status/${requestId}`);
        const urls = (res.images?.length ? res.images.map(i => i.r2_url) : res.result?.image_urls || []).filter(Boolean);
        if (res.status === 'done' && urls.length) {
          if (cell) { const img = cell.querySelector('img'); const ldr = cell.querySelector('.loader'); if (ldr) ldr.classList.add('hidden'); if (img) { img.src = urls[0]; img.classList.remove('hidden', 'opacity-0', 'scale-110'); img.classList.add('opacity-100'); } }
          return;
        }
        if (res.status === 'failed') { if (cell) { cell.querySelector('.loader')?.classList.add('hidden'); cell.style.boxShadow = 'inset 0 0 40px rgba(239,68,68,0.2)'; } return; }
      } catch (e) { /* retry */ }
      await sleep(pollDelay);
    }
  }

  function rollOracle() {
    const idx = Math.floor(Math.random() * ORACLE_PROMPTS.length);
    const p = dom.prompt(), n = dom.negativePrompt(), a = dom.aspect(), q = dom.quality();
    if (p) p.value = ORACLE_PROMPTS[idx];
    if (n) n.value = 'worst quality, low quality, bad anatomy, deformed, watermark, signature';
    if (a) a.value = '16:9';
    if (q) q.value = 'High Quality';
    toast('The Oracle has spoken.', 'info');
  }

  function clearPrompt() { const p = dom.prompt(), n = dom.negativePrompt(); if (p) p.value = ''; if (n) n.value = ''; toast('Vision cleared.', 'info'); }
  function pastePrompt() { navigator.clipboard.readText().then(text => { const p = dom.prompt(); if (p) p.value = text; }); }

  return { getPayload, setLoading, applyMode, renderGallery, runGeneration, runMatrixCast, pollUntilDone, rollOracle, clearPrompt, pastePrompt };
}
