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

    // 4. Premium Landing Page
    const rawUrl = `${url.origin}${url.pathname}?raw=1`;
    const homeUrl = 'https://aether-store.pages.dev';

    const html = `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aether | Divine Creation</title>
    
    <!-- Social Meta Tags -->
    <meta property="og:title" content="Aether Studio | Divine Manifestation">
    <meta property="og:description" content="Witness a vision shared from the Aether. Click to create yours.">
    <meta property="og:image" content="${rawUrl}">
    <meta property="og:type" content="website">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:image" content="${rawUrl}">

    <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&family=Outfit:wght@300;400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --accent: #8b5cf6;
            --accent-glow: rgba(139, 92, 246, 0.3);
            --bg: #030712;
        }
        body {
            margin: 0;
            padding: 0;
            background: var(--bg);
            color: white;
            font-family: 'Outfit', sans-serif;
            display: flex;
            flex-direction: column;
            align-items: center;
            min-height: 100vh;
            overflow-x: hidden;
        }
        
        /* Subtle background glow */
        body::before {
            content: '';
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: radial-gradient(circle at 50% 50%, rgba(139, 92, 246, 0.08) 0%, transparent 70%);
            pointer-events: none;
            z-index: -1;
        }

        .container {
            max-width: 800px;
            width: 100%;
            padding: 40px 20px;
            box-sizing: border-box;
            display: flex;
            flex-direction: column;
            align-items: center;
            animation: fadeIn 0.8s ease-out;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .header {
            margin-bottom: 32px;
            text-align: center;
        }

        .logo {
            font-family: 'Cinzel', serif;
            font-size: clamp(1.2rem, 5vw, 1.8rem);
            letter-spacing: 0.4em;
            color: var(--accent);
            text-decoration: none;
            text-shadow: 0 0 20px var(--accent-glow);
            transition: opacity 0.2s;
        }
        .logo:hover { opacity: 0.8; }

        .image-card {
            position: relative;
            width: 100%;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 28px;
            padding: 12px;
            box-sizing: border-box;
            backdrop-filter: blur(10px);
            box-shadow: 0 30px 60px rgba(0,0,0,0.6);
            margin-bottom: 40px;
        }

        .image-inner {
            width: 100%;
            border-radius: 20px;
            overflow: hidden;
            display: block;
            line-height: 0;
            background: #000;
        }

        img {
            width: 100%;
            height: auto;
            display: block;
        }

        .cta-section {
            width: 100%;
            text-align: center;
        }

        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 18px 48px;
            background: white;
            color: #000;
            text-decoration: none;
            border-radius: 100px;
            font-weight: 600;
            font-size: 1rem;
            letter-spacing: 0.02em;
            transition: all 0.3s cubic-bezier(0.23, 1, 0.32, 1);
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }

        .btn:hover {
            transform: scale(1.05);
            background: var(--accent);
            color: white;
            box-shadow: 0 15px 40px var(--accent-glow);
        }

        .footer {
            margin-top: auto;
            padding: 40px 0;
            font-size: 0.7rem;
            color: rgba(255,255,255,0.3);
            letter-spacing: 0.2em;
            text-transform: uppercase;
        }

        /* Responsive Tweaks */
        @media (max-width: 600px) {
            .container { padding: 30px 16px; }
            .image-card { border-radius: 20px; padding: 8px; }
            .image-inner { border-radius: 14px; }
            .btn { width: 100%; box-sizing: border-box; padding: 16px 24px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <a href="${homeUrl}" class="logo">AETHER</a>
        </div>
        
        <div class="image-card">
            <div class="image-inner">
                <img src="${rawUrl}" alt="Divine Manifestation">
            </div>
        </div>

        <div class="cta-section">
            <a href="${homeUrl}" class="btn">Create Your Vision</a>
        </div>

        <div class="footer">
            Aether Studio &bull; Divine AI Engine
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
