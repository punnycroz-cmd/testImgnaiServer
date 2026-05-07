export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const parts = url.pathname.split('/');
    
    // Pattern: /s/{shortcode}
    if (parts[1] !== 's' || !parts[2]) {
      return new Response('Not found', { status: 404 });
    }
    
    const shortcode = parts[2];
    const isRaw = url.searchParams.has('raw');

    // 1. Retrieve the r2_key from KV
    const r2Key = await env.SHARE_KV.get(shortcode);
    if (!r2Key) {
      return new Response('Invalid or expired share link', { status: 404 });
    }

    // 2. Fetch the image from R2
    const object = await env.IMAGES.get(r2Key);
    if (!object) {
      return new Response('Image not found', { status: 404 });
    }

    // 3. Raw image for previews/embedding
    if (isRaw) {
      return new Response(object.body, {
        headers: {
          'Content-Type': object.httpMetadata?.contentType || 'image/png',
          'Cache-Control': 'public, max-age=86400',
        },
      });
    }

    // 4. Ultra-Premium Gallery Page
    const rawUrl = `${url.origin}${url.pathname}?raw=1`;
    const homeUrl = 'https://aether-store.pages.dev';
    const displayId = shortcode.toUpperCase();
    const date = new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

    const html = `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Aether | Divine Manifestation ${displayId}</title>
    
    <!-- Social Meta Tags -->
    <meta property="og:title" content="Aether Studio | Vision ${displayId}">
    <meta property="og:description" content="Witness a divine manifestation from the Aether.">
    <meta property="og:image" content="${rawUrl}">
    <meta property="og:type" content="website">
    <meta name="twitter:card" content="summary_large_image">

    <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&family=Outfit:wght@300;400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --accent: #8b5cf6;
            --accent-soft: rgba(139, 92, 246, 0.4);
            --bg: #030610;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            padding: 0;
            background: var(--bg);
            color: white;
            font-family: 'Outfit', sans-serif;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100vh;
            height: 100dvh;
            overflow: hidden;
            -webkit-font-smoothing: antialiased;
        }
        
        /* Cosmic Background Overlay */
        body::before {
            content: '';
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: 
                radial-gradient(circle at 20% 20%, rgba(139, 92, 246, 0.05) 0%, transparent 40%),
                radial-gradient(circle at 80% 80%, rgba(99, 102, 241, 0.05) 0%, transparent 40%);
            z-index: -1;
        }

        .container {
            width: 100%;
            max-width: 1000px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: space-between;
            padding: 24px;
            height: 100%;
            animation: fadeIn 1s cubic-bezier(0.2, 0, 0.2, 1);
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: scale(0.98); }
            to { opacity: 1; transform: scale(1); }
        }

        .header {
            text-align: center;
            flex-shrink: 0;
        }

        .logo {
            font-family: 'Cinzel', serif;
            font-size: 1.2rem;
            letter-spacing: 0.5em;
            color: var(--accent);
            text-decoration: none;
            text-shadow: 0 0 25px var(--accent-soft);
        }

        .manifest-info {
            font-size: 0.65rem;
            letter-spacing: 0.2em;
            color: rgba(255,255,255,0.3);
            text-transform: uppercase;
            margin-top: 8px;
        }

        .gallery-card {
            flex-grow: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            width: 100%;
            max-height: 72vh;
            padding: 20px 0;
        }

        .image-container {
            position: relative;
            max-height: 100%;
            max-width: 100%;
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 8px;
            box-shadow: 0 40px 100px rgba(0,0,0,0.8);
            backdrop-filter: blur(20px);
        }

        img {
            max-width: 100%;
            max-height: calc(72vh - 18px);
            border-radius: 14px;
            display: block;
            object-fit: contain;
        }

        /* Scanline effect over image */
        .image-container::after {
            content: '';
            position: absolute;
            inset: 8px;
            border-radius: 14px;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.1) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.02), rgba(0, 255, 0, 0.01), rgba(0, 0, 255, 0.02));
            background-size: 100% 3px, 3px 100%;
            pointer-events: none;
            opacity: 0.3;
        }

        .actions {
            flex-shrink: 0;
            text-align: center;
            width: 100%;
            padding-bottom: 20px;
        }

        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 18px 48px;
            background: linear-gradient(135deg, #fff 0%, #e2e8f0 100%);
            color: #000;
            text-decoration: none;
            border-radius: 100px;
            font-weight: 600;
            font-size: 0.95rem;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            transition: all 0.4s cubic-bezier(0.165, 0.84, 0.44, 1);
            box-shadow: 0 10px 40px rgba(0,0,0,0.4);
        }

        .btn:hover {
            transform: translateY(-4px) scale(1.02);
            background: var(--accent);
            color: white;
            box-shadow: 0 20px 40px var(--accent-soft);
        }

        .badge {
            display: block;
            margin-top: 16px;
            font-size: 0.6rem;
            color: rgba(255,255,255,0.25);
            letter-spacing: 0.15em;
            text-transform: uppercase;
        }

        @media (max-width: 600px) {
            .gallery-card { max-height: 60vh; }
            img { max-height: calc(60vh - 18px); }
            .btn { width: 100%; padding: 18px 24px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <a href="${homeUrl}" class="logo">AETHER STUDIO</a>
            <div class="manifest-info">Manifestation #${displayId} &bull; ${date}</div>
        </div>
        
        <div class="gallery-card">
            <div class="image-container">
                <img src="${rawUrl}" alt="Aether Manifestation">
            </div>
        </div>

        <div class="actions">
            <a href="${homeUrl}" class="btn">Begin Your Creation</a>
            <div class="badge">Decentralized Vision Engine &bull; v2.0</div>
        </div>
    </div>
</body>
</html>
    `;

    return new Response(html, {
      headers: {
        'Content-Type': 'text/html;charset=UTF-8',
        'Cache-Control': 'public, max-age=3600',
      },
    });
  },
};
