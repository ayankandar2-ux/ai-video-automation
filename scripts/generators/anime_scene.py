"""
Generator: anime_scene
Produces a video from N AI-illustrated still images, each animated with a
slow pan/zoom (Ken Burns) effect, stitched together, with music overlaid.

Image generation tries Gemini first, then falls back to NVIDIA's hosted
Stable Diffusion 3 endpoint if Gemini fails (quota/auth/safety-filter
issues). If both fail, the caller (run_pipeline.py) falls back further to
the macro_abstract generator.

Requires env var: GEMINI_API_KEY (primary)
Optional env var: NVIDIA_API_KEY (fallback - get a free one at
    https://build.nvidia.com/settings/api-keys)

Usage:
    python anime_scene.py --out output.mp4 --prompt-theme "space battle, cosmic horror"
"""
import argparse
import os
import sys
import tempfile
import base64

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "utils"))
from ffmpeg_helpers import (
    image_to_kenburns_clip, concat_clips, add_audio, pick_random_music, run,
)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"  # update if a newer image model is available

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY")
NVIDIA_SD3_URL = "https://ai.api.nvidia.com/v1/genai/stabilityai/stable-diffusion-3-medium"

# Base style locked in so every scene looks consistent, regardless of theme.
STYLE_SUFFIX = (
    ", dark moody anime illustration style, cinematic lighting, high detail, "
    "dramatic color grading, vertical 9:16 composition, no text, no watermark"
)


def _generate_image_gemini(prompt, out_path, max_retries=4):
    """Call the Gemini image generation API and save the result to out_path.
    Retries with exponential backoff on rate limits (429) and transient server errors.
    """
    import requests
    import time

    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set.")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_IMAGE_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    last_error = None
    last_no_image_reason = None
    current_prompt = prompt

    for attempt in range(1, max_retries + 1):
        payload = {"contents": [{"parts": [{"text": current_prompt + STYLE_SUFFIX}]}]}
        resp = requests.post(url, json=payload, timeout=120)
        if resp.status_code == 429 or resp.status_code >= 500:
            wait = min(60, 2 ** attempt)  # 2s, 4s, 8s, 16s... capped at 60s
            print(f"[gemini] {resp.status_code} on attempt {attempt}/{max_retries}, retrying in {wait}s")
            last_error = resp
            time.sleep(wait)
            continue
        if resp.status_code == 401 or resp.status_code == 403:
            # Not retryable - key is invalid/revoked. Fail fast so the caller
            # can move on to the NVIDIA fallback instead of burning time here.
            raise RuntimeError(f"Gemini auth failed ({resp.status_code}): {resp.text[:300]}")
        resp.raise_for_status()
        data = resp.json()

        candidates = data.get("candidates") or []
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        image_part = next((p for p in parts if "inlineData" in p), None)

        if image_part is None:
            # No image came back - most commonly the prompt tripped a safety
            # filter and Gemini replied with text (or an empty/blocked candidate)
            # instead of refusing outright with an HTTP error. Don't crash: log
            # what we actually got, back off, and retry with a softened prompt.
            finish_reason = candidates[0].get("finishReason") if candidates else "NO_CANDIDATES"
            text_reply = next((p.get("text") for p in parts if "text" in p), None)
            last_no_image_reason = f"finishReason={finish_reason} text={text_reply!r}"
            print(f"[gemini] no image in response on attempt {attempt}/{max_retries}: {last_no_image_reason}")

            if attempt < max_retries:
                wait = min(30, 2 ** attempt)
                # Soften the prompt in case a specific word tripped the filter -
                # drop it back to something generic and safe.
                current_prompt = f"{prompt.split(',')[0]}, safe for all audiences"
                time.sleep(wait)
                continue
            raise RuntimeError(
                f"Gemini returned no image after {max_retries} attempts. "
                f"Last response: {last_no_image_reason}"
            )

        img_bytes = base64.b64decode(image_part["inlineData"]["data"])
        with open(out_path, "wb") as f:
            f.write(img_bytes)
        return out_path

    last_error.raise_for_status()  # exhausted retries on HTTP errors - raise the last one clearly


def _generate_image_nvidia(prompt, out_path, max_retries=3):
    """Fallback image generation via NVIDIA's hosted Stable Diffusion 3
    endpoint (free tier at build.nvidia.com). Used when Gemini fails.
    """
    import requests
    import time

    if not NVIDIA_API_KEY:
        raise RuntimeError("NVIDIA_API_KEY environment variable is not set.")

    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    payload = {
        "prompt": (prompt + STYLE_SUFFIX)[:9900],  # API caps prompt length at 10000 chars
        "mode": "text-to-image",
        "model": "sd3",
        "aspect_ratio": "9:16",
        "steps": 30,
        "cfg_scale": 5,
        "output_format": "jpeg",
        "seed": 0,
    }

    last_error = None
    for attempt in range(1, max_retries + 1):
        resp = requests.post(NVIDIA_SD3_URL, headers=headers, json=payload, timeout=120)
        if resp.status_code == 429 or resp.status_code >= 500:
            wait = min(30, 2 ** attempt)
            print(f"[nvidia] {resp.status_code} on attempt {attempt}/{max_retries}, retrying in {wait}s")
            last_error = resp
            time.sleep(wait)
            continue
        resp.raise_for_status()

        # Response shape isn't 100% pinned down across NVIDIA's API versions -
        # handle the couple of formats their docs/examples show.
        data = resp.json()
        img_b64 = None
        if isinstance(data.get("image"), str):
            img_b64 = data["image"]
        elif data.get("artifacts"):
            img_b64 = data["artifacts"][0].get("base64")
        elif data.get("data"):
            img_b64 = data["data"][0].get("b64_json")

        if not img_b64:
            raise RuntimeError(f"NVIDIA response had no recognizable image field: {str(data)[:300]}")

        img_bytes = base64.b64decode(img_b64)
        with open(out_path, "wb") as f:
            f.write(img_bytes)
        return out_path

    last_error.raise_for_status()


def generate_image(prompt, out_path, max_retries=4):
    """Generate an image for a scene, trying Gemini first and falling back
    to NVIDIA's free Stable Diffusion endpoint if Gemini fails outright
    (quota exhaustion, revoked key, persistent safety-filter block, etc).
    Raises only if both providers fail (or NVIDIA_API_KEY isn't configured).
    """
    try:
        return _generate_image_gemini(prompt, out_path, max_retries=max_retries)
    except Exception as gemini_err:
        if not NVIDIA_API_KEY:
            raise
        print(f"[fallback] Gemini image generation failed ({gemini_err}); trying NVIDIA SD3")
        try:
            return _generate_image_nvidia(prompt, out_path)
        except Exception as nvidia_err:
            raise RuntimeError(
                f"Both image providers failed. Gemini: {gemini_err} | NVIDIA: {nvidia_err}"
            )


def build_video(theme, num_scenes, scene_duration, out_path, music_dir, resolution, fps):
    with tempfile.TemporaryDirectory() as tmp:
        clip_paths = []
        for i in range(num_scenes):
            img_path = os.path.join(tmp, f"scene_{i}.png")
            clip_path = os.path.join(tmp, f"scene_{i}.mp4")

            # Each scene gets its own beat of the theme - customize this prompt
            # list per-theme if you want more narrative control.
            scene_prompt = f"{theme}, scene {i+1} of {num_scenes}"
            generate_image(scene_prompt, img_path)

            direction = "in" if i % 2 == 0 else "out"
            image_to_kenburns_clip(
                img_path, clip_path, scene_duration,
                resolution=resolution, fps=fps, zoom_direction=direction,
            )
            clip_paths.append(clip_path)

        silent_path = os.path.join(tmp, "silent.mp4")
        concat_clips(clip_paths, silent_path)

        music_path = pick_random_music(music_dir)
        if not music_path:
            raise RuntimeError(
                f"No music files found in '{music_dir}'. Add at least one .mp3/.wav "
                f"file there before running - silent videos aren't acceptable per spec."
            )
        add_audio(silent_path, music_path, out_path)

    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--prompt-theme", default="cosmic space battle, nebula, warrior silhouette")
    parser.add_argument("--scenes", type=int, default=4)
    parser.add_argument("--total-duration", type=int, default=20)
    parser.add_argument("--music-dir", default="assets/music")
    parser.add_argument("--resolution", default="1080x1920")
    parser.add_argument("--fps", type=int, default=30)
    args = parser.parse_args()

    per_scene = max(2, args.total_duration // args.scenes)
    build_video(
        args.prompt_theme, args.scenes, per_scene, args.out,
        args.music_dir, args.resolution, args.fps,
    )
    print(f"Done: {args.out}")
