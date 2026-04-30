export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const parts = url.pathname.split('/');
    
    // Pattern: /s/{shortcode}
    if (parts[1] !== 's' || !parts[2]) {
      return new Response('Not found', { status: 404 });
    }
    
    const shortcode = parts[2];

    // 1. Retrieve the private r2_key from KV
    const r2Key = await env.SHARE_KV.get(shortcode);
    if (!r2Key) {
      return new Response('Invalid or expired share link', { status: 404 });
    }

    // 2. Fetch the image from R2 using the private binding
    const object = await env.IMAGES.get(r2Key);
    if (!object) {
      return new Response('Image not found', { status: 404 });
    }

    // 3. (Optional) Fire-and-forget analytics
    const ip = request.headers.get('CF-Connecting-IP') || 'unknown';
    const ua = request.headers.get('User-Agent') || '';
    
    // We use a helper to hash the IP for privacy
    const ipHash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(ip))
      .then(hash => Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, '0')).join(''));

    // Fire non-blocking request to the backend
    fetch('https://YOUR_BACKEND_URL/api/track_click', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ shortcode, ip_hash: ipHash, user_agent: ua })
    }).catch(() => {});

    // 4. Return the image directly
    return new Response(object.body, {
      headers: {
        'Content-Type': object.httpMetadata?.contentType || 'image/png',
        'Cache-Control': 'public, max-age=86400',
        'X-Content-Type-Options': 'nosniff',
      },
    });
  },
};
