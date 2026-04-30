/* ============================================
   Aether Studio — Aether Particles Canvas
   Background particle overlay
   ============================================ */

/**
 * Initialize the ambient particle canvas
 * @param {import('../store.js').AppState} state
 */
export function initAetherCanvas(state) {
  const canvas = document.getElementById('aetherCanvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  let width, height;
  const particles = [];
  let animationId = null;

  function resize() {
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = width;
    canvas.height = height;
  }

  window.addEventListener('resize', resize);
  resize();

  // Create particles
  for (let i = 0; i < 40; i++) {
    particles.push({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.3,
      vy: (Math.random() - 0.5) * 0.3,
      size: Math.random() * 2 + 0.5,
      shift: Math.random() * Math.PI * 2,
    });
  }

  function animate() {
    // Pause when tab is hidden for performance
    if (!state.get('app.isTabVisible')) {
      animationId = requestAnimationFrame(animate);
      return;
    }

    ctx.clearRect(0, 0, width, height);
    const isNsfw = state.get('app.mode') === 'nsfw';

    particles.forEach(p => {
      p.x += p.vx;
      p.y += p.vy;
      p.shift += 0.01;

      if (p.x < 0) p.x = width;
      if (p.x > width) p.x = 0;
      if (p.y < 0) p.y = height;
      if (p.y > height) p.y = 0;

      const alpha = (Math.sin(p.shift) * 0.3) + 0.3;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      ctx.fillStyle = isNsfw
        ? `rgba(139, 92, 246, ${alpha})`
        : `rgba(16, 185, 129, ${alpha})`;
      ctx.fill();
    });

    animationId = requestAnimationFrame(animate);
  }

  animate();

  // Cleanup function
  return () => {
    if (animationId) cancelAnimationFrame(animationId);
  };
}
