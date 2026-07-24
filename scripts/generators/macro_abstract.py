"""
Generator: macro_abstract
Produces a video by pulling a free stock clip (Pexels) matching a query,
trimming it to length, and overlaying music.

Requires env var: PEXELS_API_KEY (free - get one at https://www.pexels.com/api/)

Usage:
    python macro_abstract.py --out output.mp4 --query "ink water macro abstract" --duration 20
"""
import argparse
import os
import sys
import tempfile
import requests

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "utils"))
from ffmpeg_helpers import trim_clip, add_audio, pick_random_music, run

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"


def find_stock_clip(query, min_duration=10):
    if not PEXELS_API_KEY:
        raise RuntimeError("PEXELS_API_KEY environment variable is not set.")

    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": 15, "orientation": "portrait"}
    resp = requests.get(PEXELS_SEARCH_URL, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    candidates = [v for v in data.get("videos", []) if v["duration"] >= min_duration]
    if not candidates:
        candidates = data.get("videos", [])
    if not candidates:
        raise RuntimeError(f"No stock clips found for query: {query}")

    video = candidates[0]
    # Prefer the highest-resolution HD file available.
    files = sorted(video["video_files"], key=lambda f: f.get("height", 0), reverse=True)
    return files[0]["link"]


def download(url, out_path):
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    return out_path


def build_video(query, duration, out_path, music_dir):
    with tempfile.TemporaryDirectory() as tmp:
        raw_path = os.path.join(tmp, "raw.mp4")
        trimmed_path = os.path.join(tmp, "trimmed.mp4")

        clip_url = find_stock_clip(query, min_duration=duration)
        download(clip_url, raw_path)
        trim_clip(raw_path, trimmed_path, duration)

        music_path = pick_random_music(music_dir)
        if not music_path:
            raise RuntimeError(
                f"No music files found in '{music_dir}'. Add at least one .mp3/.wav "
                f"file there before running - silent videos aren't acceptable per spec."
            )
        add_audio(trimmed_path, music_path, out_path)

    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--query", default="ink water macro abstract")
    parser.add_argument("--duration", type=int, default=20)
    parser.add_argument("--music-dir", default="assets/music")
    args = parser.parse_args()

    build_video(args.query, args.duration, args.out, args.music_dir)
    print(f"Done: {args.out}")
