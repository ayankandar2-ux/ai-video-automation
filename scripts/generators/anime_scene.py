"""
Generator: anime_scene
Produces a video from N AI-illustrated still images, each animated with a
slow pan/zoom (Ken Burns) effect, stitched together, with music overlaid.

Requires env var: GEMINI_API_KEY

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

# Base style locked in so every scene looks consistent, regardless of theme.
STYLE_SUFFIX = (
    ", dark moody anime illustration style, cinematic lighting, high detail, "
    "dramatic color grading, vertical 9:16 composition, no text, no watermark"
)


def generate_image(prompt, out_path):
    """Call the Gemini image generation API and save the result to out_path."""
    import requests

    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set.")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_IMAGE_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = {"contents": [{"parts": [{"text": prompt + STYLE_SUFFIX}]}]}
    resp = requests.post(url, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()

    # Pull the first inline image out of the response.
    parts = data["candidates"][0]["content"]["parts"]
    image_part = next(p for p in parts if "inlineData" in p)
    img_bytes = base64.b64decode(image_part["inlineData"]["data"])
    with open(out_path, "wb") as f:
        f.write(img_bytes)
    return out_path


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
        if music_path:
            add_audio(silent_path, music_path, out_path)
        else:
            run(["cp", silent_path, out_path])

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
