class GenerateDefaults:
    MODEL = "Gen"
    COUNT = 4
    ASPECT = "1:1"
    QUALITY = "Fast"
    NSFW = False
    NEGATIVE_PROMPT = ""
    REALM = "day"


ASPECT_TO_RESOLUTION = {
    "1:1": "BOX_X_LARGE",
    "16:9": "LANDSCAPE",
    "5:2": "WIDE_LARGE",
    "4:5": "PORTRAIT",
    "4:7": "TALL_LARGE",
}

QUALITY_CHOICES = ["Fast", "High Quality", "4k+"]
ASPECT_CHOICES = ["1:1", "16:9", "5:2", "4:5", "4:7"]

MODEL_CONFIGS = {
    "Ani": {"profile": "ani", "n_steps": 32, "guidance_scale": 8.5, "strength": 0.76, "negative_prompt": "text, watermark, blurry, monochrome, sketch, line art, drawing, pencil art, pen art, watermark, signature, low quality, bad quality"},
    "Aura": {"profile": "aura", "n_steps": 36, "guidance_scale": 5, "strength": 0.76, "negative_prompt": "score_6, score_5, score_4, low res, huge breasts, mutated hands, bad hands, monochrome, grayscale, old, ugly, jewelry, accessory, bad eyes, bad face, muscular, chibi, buzzcut, watermark, logo"},
    "Evo": {"profile": "evo", "n_steps": 40, "guidance_scale": 7, "strength": 0.76, "negative_prompt": "(worst quality, low quality, illustration, 3d, 2d, painting, cartoons, sketch), open mouth, watermark)"},
    "Flux1 D": {"profile": "flux1d", "n_steps": 35, "guidance_scale": 3.5, "strength": 0.76, "negative_prompt": ""},
    "Fur": {"profile": "fur", "n_steps": 25, "guidance_scale": 4.5, "strength": 0.76, "negative_prompt": "human, multiple tails, old, oldest, cartoon, graphic, text, painting, crayon, graphite, abstract, glitch, deformed, mutated, ugly, disfigured, long body, lowres, bad anatomy, bad hands, missing fingers, extra digits, fewer digits, very displeasing, (worst"},
    "FurXL Classic": {"profile": "furxl", "n_steps": 40, "guidance_scale": 7, "strength": 0.76, "negative_prompt": "(worst quality, low quality), watermarks, signature, (interlocked fingers)"},
    "Gen": {"profile": "gen", "n_steps": 30, "guidance_scale": 3.5, "strength": 0.76, "negative_prompt": "low quality, bad quality, mutated, low detail, blurry, out of focus, jpeg artifacts, bad anatomy, mutated hands, deformed hands, too many fingers, extra legs, extra arms, deformed feet, bad feet"},
    "Glitch": {"profile": "glitch", "n_steps": 30, "guidance_scale": 5, "strength": 0.76, "negative_prompt": "loli, young, petite, patreon, bad anatomy, bad hands, error, missing fingers, extra digit, fewer digits, cropped,long legs,signature, patreon username, patreon logo"},
    "Gothic": {"profile": "gothic", "n_steps": 30, "guidance_scale": 5, "strength": 0.76, "negative_prompt": "3d, Negative prompt: worst_quality, bad_quality, poorly_detailed, 2d, sketch, ugly face, low res, interlocked fingers, anatomically incorrect hands, bad anatomy, {worst quality, low quality, normal quality}, (watermark, signature, letter, username, logo, "},
    "Hyper CGI": {"profile": "hypercgi", "n_steps": 25, "guidance_scale": 3, "strength": 0.76, "negative_prompt": "SmoothNegative_Hands-neg, Smooth Negative, modern, recent, old, oldest, cartoon, graphic, text, painting, crayon, graphite, abstract, glitch, deformed, mutated, ugly, disfigured, long body, lowres, bad anatomy, bad hands, missing fingers, extra fingers, e"},
    "HyperX": {"profile": "hyperx", "n_steps": 28, "guidance_scale": 7, "strength": 0.76, "negative_prompt": "blur, bad quality, bad composition, copyright, watermark, lineart, pixelated, pixelart, drawing, painting, sketch"},
    "Muse": {"profile": "muse", "n_steps": 28, "guidance_scale": 3, "strength": 0.76, "negative_prompt": ""},
    "Nai": {"profile": "nai", "n_steps": 50, "guidance_scale": 7, "strength": 0.76, "negative_prompt": "child, loli, young, source_furry, source_pony, monochrome, 3d, censored, (worst quality, low quality:1.4), (jpeg artifacts:1.4), negative_hand, negative_hand-neg, watermark, signature, text"},
    "Neo": {"profile": "neo", "n_steps": 35, "guidance_scale": 4, "strength": 0.76, "negative_prompt": ""},
    "Noob": {"profile": "noob", "n_steps": 32, "guidance_scale": 5, "strength": 0.76, "negative_prompt": "worst quality, old, early, low quality, lowres, signature, username, logo, bad hands, mutated hands, mammal, anthro, furry, ambiguous form, feral, semi-anthro"},
    "Pixel": {"profile": "pixel", "n_steps": 26, "guidance_scale": 3.5, "strength": 0.76, "negative_prompt": "bad quality, worst quality, worst detail, copyright name, bad anatomy, watermark"},
    "Pony": {"profile": "pony", "n_steps": 30, "guidance_scale": 6, "strength": 0.76, "negative_prompt": "score_6, score_5, score_4, nsfw, pumpkin, 3d, blurry, cropped, signature, username, watermark, jpeg artifacts, normal quality, worst quality, low quality, (missing fingers, extra digits, extra fingers, fewer digits, bad hands:1.3), bad eye,(deformed, dist"},
    "Rend": {"profile": "rend", "n_steps": 40, "guidance_scale": 6, "strength": 0.76, "negative_prompt": "worst_quality, bad_quality, poorly_detailed, long neck"},
    "Retro": {"profile": "retro", "n_steps": 30, "guidance_scale": 5, "strength": 0.76, "negative_prompt": "worst quality, low quality, lowres, bad anatomy, bad hands, text, error, missing fingers, extra digits, fewer digits, cropped, jpeg artifacts, signature, watermark, username, blurry, artist name, old, early, lowres, logo, mutated hands, mammal, anthro, fu"},
    "Supra": {"profile": "supra", "n_steps": 50, "guidance_scale": 2, "strength": 0.76, "negative_prompt": "(deformed iris, deformed pupils), worst quality, low quality, blurry, text"},
    "Synth": {"profile": "synth", "n_steps": 40, "guidance_scale": 5, "strength": 0.76, "negative_prompt": "bad quality, worst quality, worst detail, censor, bad anatomy, patreon, name, signature, child, underage, loli"},
    "Toon": {"profile": "toon", "n_steps": 53, "guidance_scale": 7, "strength": 0.76, "negative_prompt": "score_6, score_5, score_4, ugly face, mutated hands, ahegao, bad eyes, monochrome, sketch, ugly style"},
    "Volt": {"profile": "volt", "n_steps": 30, "guidance_scale": 7, "strength": 0.76, "negative_prompt": "bad quality, poor quality, disfigured, jpg, toy, bad anatomy, missing limbs, missing fingers, ugly, scary, watermark"},
    "Wassie": {"profile": "wassie", "n_steps": 40, "guidance_scale": 7, "strength": 0.76, "negative_prompt": "wrong,imperfect hands, painting, sketch, concept art, cross-eyed,sketches, (worst quality:2), (low quality:2), (normal quality:2), lowres, normal quality, skin spots, acnes, skin blemishes, bad anatomy, DeepNegative, facing away, tilted head, lowres, bad "},
}

MODEL_ORDER = ["Gen", "Ani", "Synth", "Fur", "Noob", "Aura", "Pixel", "Hyper CGI", "Volt", "Muse", "Gothic", "Rend", "Retro", "Pony", "Neo", "Nai", "Glitch", "Flux1 D", "Supra", "Evo", "Toon", "Wassie", "HyperX", "FurXL Classic"]

STAR_MODEL_CONFIGS = {
    "Gen": {"profile": "gen", "n_steps": 30, "guidance_scale": 3.5, "strength": 0.76, "negative_prompt": "low quality, bad quality, mutated, low detail, blurry, out of focus, jpeg artifacts, bad anatomy, mutated hands, deformed hands, too many fingers, extra legs, extra arms, deformed feet, bad feet"},
    "Ani": {"profile": "ani", "n_steps": 32, "guidance_scale": 8.5, "strength": 0.76, "negative_prompt": "text, watermark, blurry, monochrome, sketch, line art, drawing, pencil art, pen art, watermark, signature, low quality, bad quality"},
    "Synth": {"profile": "synth", "n_steps": 40, "guidance_scale": 5, "strength": 0.76, "negative_prompt": "bad quality, worst quality, worst detail, censor, bad anatomy, patreon, name, signature, child, underage, loli"},
    "Fur": {"profile": "fur", "n_steps": 25, "guidance_scale": 4.5, "strength": 0.76, "negative_prompt": "human, multiple tails, old, oldest, cartoon, graphic, text, painting, crayon, graphite, abstract, glitch, deformed, mutated, ugly, disfigured, long body, lowres, bad anatomy, bad hands, missing fingers, extra digits, fewer digits"},
    "Noob": {"profile": "noob", "n_steps": 32, "guidance_scale": 5, "strength": 0.76, "negative_prompt": "worst quality, old, early, low quality, lowres, signature, username, logo, bad hands, mutated hands, mammal, anthro, furry, ambiguous form, feral, semi-anthro"},
    "Aura": {"profile": "aura", "n_steps": 36, "guidance_scale": 5, "strength": 0.76, "negative_prompt": "score_6, score_5, score_4, low res, huge breasts, mutated hands, bad hands, monochrome, grayscale, old, ugly, jewelry, accessory, bad eyes, bad face, muscular, chibi, buzzcut, watermark, logo"},
    "Pixel": {"profile": "pixel", "n_steps": 26, "guidance_scale": 3.5, "strength": 0.76, "negative_prompt": "bad quality, worst quality, worst detail, copyright name, bad anatomy, watermark"},
    "Hyper CGI": {"profile": "hypercgi", "n_steps": 25, "guidance_scale": 3, "strength": 0.76, "negative_prompt": "SmoothNegative_Hands-neg, Smooth Negative, modern, recent, old, oldest, cartoon, graphic, text, painting, crayon, graphite, abstract, glitch, deformed, mutated, ugly, disfigured, long body, lowres, bad anatomy, bad hands, missing fingers, extra fingers"},
    "Volt": {"profile": "volt", "n_steps": 30, "guidance_scale": 7, "strength": 0.76, "negative_prompt": "bad quality, poor quality, disfigured, jpg, toy, bad anatomy, missing limbs, missing fingers, ugly, scary, watermark"},
    "Muse": {"profile": "muse", "n_steps": 28, "guidance_scale": 3, "strength": 0.76, "negative_prompt": ""},
    "Rend": {"profile": "rend", "n_steps": 40, "guidance_scale": 6, "strength": 0.76, "negative_prompt": "worst_quality, bad_quality, poorly_detailed, long neck"},
    "Pony": {"profile": "pony", "n_steps": 30, "guidance_scale": 6, "strength": 0.76, "negative_prompt": "score_6, score_5, score_4, nsfw, pumpkin, 3d, blurry, cropped, signature, username, watermark, jpeg artifacts, normal quality, worst quality, low quality"},
    "Neo": {"profile": "neo", "n_steps": 35, "guidance_scale": 4, "strength": 0.76, "negative_prompt": ""},
    "Nai": {"profile": "nai", "n_steps": 50, "guidance_scale": 7, "strength": 0.76, "negative_prompt": "child, loli, young, source_furry, source_pony, monochrome, 3d, censored, (worst quality, low quality:1.4), (jpeg artifacts:1.4), negative_hand, watermark, signature, text"},
    "Retro": {"profile": "retro", "n_steps": 30, "guidance_scale": 5, "strength": 0.76, "negative_prompt": "worst quality, low quality, lowres, bad anatomy, bad hands, text, error, missing fingers, extra digits, fewer digits, cropped, jpeg artifacts, signature, watermark, username, blurry, artist name, old, early, lowres, logo, mutated hands, mammal, anthro, furry"},
    "Supra": {"profile": "supra", "n_steps": 50, "guidance_scale": 2, "strength": 0.76, "negative_prompt": "(deformed iris, deformed pupils), worst quality, low quality, blurry, text"},
    "Evo": {"profile": "evo", "n_steps": 40, "guidance_scale": 7, "strength": 0.76, "negative_prompt": "(worst quality, low quality, illustration, 3d, 2d, painting, cartoons, sketch), open mouth, watermark"},
    "Toon": {"profile": "toon", "n_steps": 53, "guidance_scale": 7, "strength": 0.76, "negative_prompt": "score_6, score_5, score_4, ugly face, mutated hands, ahegao, bad eyes, monochrome, sketch, ugly style"},
    "HyperX": {"profile": "hyperx", "n_steps": 28, "guidance_scale": 7, "strength": 0.76, "negative_prompt": "blur, bad quality, bad composition, copyright, watermark, lineart, pixelated, pixelart, drawing, painting, sketch"},
    "FurXL Classic": {"profile": "furxl", "n_steps": 40, "guidance_scale": 7, "strength": 0.76, "negative_prompt": "(worst quality, low quality), watermarks, signature, (interlocked fingers)"},
    "Illustrious": {"profile": "illustrious", "n_steps": 53, "guidance_scale": 7, "strength": 0.76, "negative_prompt": "bad quality, worst quality, worst detail, sketch, censor, signature, watermark, patreon username, patreon logo"},
    "Real Amateurs": {"profile": "real_amateurs", "n_steps": 25, "guidance_scale": 3.5, "strength": 0.76, "negative_prompt": "asymmetrical-eyes, mismatched eyes, deformed eyes, (turkey-neck:1.2)"},
    "RealX": {"profile": "realx", "n_steps": 30, "guidance_scale": 5, "strength": 0.76, "negative_prompt": "CyberRealistic_Negative_PONY_V2, watermark, logo, label"},
    "Real Classic": {"profile": "realclassic", "n_steps": 28, "guidance_scale": 7, "strength": 0.76, "negative_prompt": "watermark, logomark, text, score 1, score 2, score 3, text, cartoon, anime, worst quality, low quality, bad anatomy, bad hands, bad eyes"},
}
