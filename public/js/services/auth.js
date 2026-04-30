/* ============================================
   Aether Studio — Auth Service
   Google OAuth + session management
   ============================================ */

/**
 * Create auth service bound to state and API
 * @param {import('../store.js').AppState} state
 * @param {{ apiFetch: Function }} api
 * @param {Function} showToast
 * @returns {Object}
 */
export function createAuthService(state, api, showToast) {

  function updateAuthUI() {
    const user = state.get('auth.user');
    const overlay = document.getElementById('auth-overlay');
    const profile = document.getElementById('user-profile');
    const avatar = document.getElementById('user-avatar');
    const name = document.getElementById('user-name');

    if (user) {
      if (overlay) overlay.classList.add('hidden');
      if (profile) profile.classList.remove('hidden');
      if (avatar) avatar.src = user.picture;
      if (name) name.textContent = user.name.split(' ')[0];
      document.querySelectorAll('.feed-user-avatar').forEach(img => img.src = user.picture);
    } else {
      if (overlay) overlay.classList.remove('hidden');
      if (profile) profile.classList.add('hidden');
    }
  }

  async function checkAuth() {
    try {
      const res = await api.apiFetch('/auth/me');
      if (res.user) {
        state.set('auth.user', res.user);
        state.set('auth.uid', res.user.uid);
        updateAuthUI();
        return true;
      } else {
        throw new Error('Not logged in');
      }
    } catch (err) {
      updateAuthUI();
      return false;
    }
  }

  async function handleGoogleLogin(response) {
    try {
      console.log('Processing Google Login...');
      const res = await api.apiFetch('/auth/google', {
        method: 'POST',
        body: JSON.stringify({ id_token: response.credential }),
      });
      state.set('auth.user', res.user);
      state.set('auth.uid', res.user.uid);
      updateAuthUI();
      showToast(`Welcome back, ${res.user.name}!`, 'info');
      return true;
    } catch (err) {
      console.error('Login failed:', err);
      showToast('Authentication failed. Please try again.', 'error');
      return false;
    }
  }

  async function logout() {
    try {
      await api.apiFetch('/auth/logout', { method: 'POST' });
      state.set('auth.user', null);
      state.set('auth.uid', 'uid_0');
      updateAuthUI();
      showToast('Logged out.', 'info');
    } catch (err) {
      console.error('Logout failed:', err);
    }
  }

  // Expose Google login handler globally for the GSI callback
  window.handleGoogleLogin = handleGoogleLogin;

  return {
    checkAuth,
    handleGoogleLogin,
    logout,
    updateAuthUI,
  };
}
