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

    // 3. If raw=1 is requested (for social previews), return the raw image
    if (isRaw) {
      return new Response(object.body, {
        headers: {
          'Content-Type': object.httpMetadata?.contentType || 'image/png',
          'Cache-Control': 'public, max-age=86400',
        },
      });
    }

    // 4. Otherwise, return a beautiful Landing Page
    const rawUrl = `${url.origin}${url.pathname}?raw=1`;
    const homeUrl = 'https://aether-store.pages.dev'; // Your main site

    const html = `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aether Studio | Divine Creation</title>
    
    <!-- Social Media Meta Tags -->
    <meta property="og:title" content="Aether Studio | Vision Shared">
    <meta property="og:description" content="A divine manifestation created in Aether Studio. Click to create yours.">
    <meta property="og:image" content="${rawUrl}">
    <meta property="og:type" content="website">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:image" content="${rawUrl}">

    <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&family=Outfit:wght@300;400;600&display=swap" rel="stylesheet">
    <style>
        body {
            margin: 0;
            padding: 0;
            background: #070a18;
            color: white;
            font-family: 'Outfit', sans-serif;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            overflow-x: hidden;
        }
        .container {
            max-width: 900px;
            width: 90%;
            text-align: center;
            padding: 40px 0;
        }
        .logo {
            font-family: 'Cinzel', serif;
            font-size: 1.5rem;
            letter-spacing: 0.3em;
            color: #8b5cf6;
            margin-bottom: 40px;
            text-decoration: none;
            display: inline-block;
        }
        .image-wrapper {
            position: relative;
            border-radius: 24px;
            overflow: hidden;
            box-shadow: 0 20px 50px rgba(0,0,0,0.5), 0 0 30px rgba(139,92,246,0.15);
            border: 1px solid rgba(255,255,255,0.1);
            margin-bottom: 40px;
        }
        img {
            max-width: 100%;
            display: block;
            height: auto;
        }
        .btn {
            display: inline-block;
            padding: 16px 40px;
            background: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%);
            color: white;
            text-decoration: none;
            border-radius: 50px;
            font-weight: 600;
            letter-spacing: 0.05em;
            box-shadow: 0 10px 20px rgba(139,92,246,0.3);
            transition: all 0.3s ease;
            text-transform: uppercase;
            font-size: 0.9rem;
        }
        .btn:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 30px rgba(139,92,246,0.4);
            filter: brightness(1.1);
        }
        .footer {
            margin-top: 60px;
            font-size: 0.8rem;
            color: rgba(255,255,255,0.4);
            letter-spacing: 0.1em;
        }
    </style>
</head>
<body>
    <div class="container">
        <a href="${homeUrl}" class="logo">AETHER STUDIO</a>
        
        <div class="image-wrapper">
            <img src="${rawUrl}" alt="Aether Manifestation">
        </div>

        <a href="${homeUrl}" class="btn">Create Your Own Manifestation</a>

        <div class="footer">
            POWERED BY AETHER ENGINE &bull; 2024
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
