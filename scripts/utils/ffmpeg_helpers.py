"""
Shared FFmpeg helpers for assembling videos from still images or clips.

Requires: ffmpeg installed and on PATH (Termux: `pkg install ffmpeg`).
"""
import os
import random
import subprocess
import glob


def run(cmd):
    """Run a shell command list, raising on failure."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
    return result


def pick_random_music(music_dir):
    """Pick a random track from the music directory. Returns None if empty."""
    tracks = glob.glob(os.path.join(music_dir, "*.mp3")) + glob.glob(
        os.path.join(music_dir, "*.wav")
    )
    if not tracks:
        return None
    return random.choice(tracks)


def image_to_kenburns_clip(image_path, out_path, duration, resolution="1080x1920",
                            fps=30, zoom_direction="in"):
    """
    Turn a still image into a short video clip with a slow pan/zoom (Ken Burns) effect.
    zoom_direction: "in" (push in, good for intense moments) or "out" (pull back, calmer).
    """
    w, h = resolution.split("x")
    total_frames = int(duration * fps)

    if zoom_direction == "in":
        zoom_expr = f"zoom+0.0015"
    else:
        zoom_expr = f"if(lte(zoom,1.0),1.3,zoom-0.0015)"

    vf = (
        f"scale=8000:-1,"
        f"zoompan=z='{zoom_expr}':d={total_frames}:s={w}x{h}:fps={fps}"
    )

    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", image_path,
        "-vf", vf,
        "-t", str(duration),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        out_path,
    ]
    run(cmd)
    return out_path


def concat_clips(clip_paths, out_path):
    """Concatenate multiple video clips (no audio) into one, using the concat demuxer."""
    list_file = out_path + ".txt"
    with open(list_file, "w") as f:
        for c in clip_paths:
            f.write(f"file '{os.path.abspath(c)}'\n")
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
        "-c", "copy", out_path,
    ]
    run(cmd)
    os.remove(list_file)
    return out_path


def add_audio(video_path, audio_path, out_path, music_volume=0.6, fade_duration=1.5):
    """Overlay a music track onto a (silent) video, trimmed to video length, with fade out."""
    video_duration = get_duration(video_path)
    fade_start = max(0, video_duration - fade_duration)
    cmd = [
        "ffmpeg", "-y", "-i", video_path, "-i", audio_path,
        "-filter_complex",
        f"[1:a]volume={music_volume},afade=t=out:st={fade_start}:d={fade_duration}[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac",
        "-shortest",
        out_path,
    ]
    run(cmd)
    return out_path


def get_duration(path):
    """Return the duration of a media file in seconds, via ffprobe."""
    import subprocess
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def trim_clip(in_path, out_path, duration, start=0):
    """Trim a stock footage clip to the target duration starting at `start` seconds."""
    cmd = [
        "ffmpeg", "-y", "-ss", str(start), "-i", in_path,
        "-t", str(duration),
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-an",
        out_path,
    ]
    run(cmd)
    return out_path


def burn_captions(video_path, srt_path, out_path):
    """Burn an .srt subtitle file into the video (optional; skip if no captions needed)."""
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", f"subtitles={srt_path}:force_style='Fontsize=18,PrimaryColour=&HFFFFFF&'",
        "-c:a", "copy",
        out_path,
    ]
    run(cmd)
    return out_path
