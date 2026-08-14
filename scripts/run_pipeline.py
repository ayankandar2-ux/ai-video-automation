"""
Main entrypoint. Run once per scheduled video (GitHub Actions calls this 4x/day).

    python scripts/run_pipeline.py --type anime_scene
    python scripts/run_pipeline.py --type macro_abstract
"""
import argparse
import os
import sys
import random
import yaml

sys.path.append(os.path.dirname(__file__))
from generators import anime_scene, macro_abstract
from uploaders import youtube, facebook, instagram

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "settings.yaml")


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def pick_type(config, forced_type=None):
    types = config["types"]
    if forced_type:
        match = next((t for t in types if t["id"] == forced_type), None)
        if not match:
            raise ValueError(f"Unknown type id: {forced_type}")
        return match
    return random.choice(types)


def generate(type_config, config, out_path):
    if type_config["id"] == "anime_scene":
        anime_scene.build_video(
            theme=random.choice([
                "cosmic space battle, nebula, warrior silhouette",
                "deep ocean bioluminescent creatures",
                "ancient ruins, mystical fog, glowing runes",
            ]),
            num_scenes=type_config["scenes"],
            scene_duration=max(2, type_config["length_seconds"] // type_config["scenes"]),
            out_path=out_path,
            music_dir=config["music"]["directory"],
            resolution=config["output"]["resolution"],
            fps=config["output"]["fps"],
        )
    elif type_config["id"] == "macro_abstract":
        macro_abstract.build_video(
            query=type_config["stock_query"],
            duration=type_config["length_seconds"],
            out_path=out_path,
            music_dir=config["music"]["directory"],
            music_prompt=type_config.get("music_prompt"),
        )
    else:
        raise ValueError(f"No generator wired up for type: {type_config['id']}")


def post_everywhere(video_path, config, title):
    dry_run = config["posting"]["dry_run"]
    results = {}
    if "youtube" in config["posting"]["platforms"]:
        results["youtube"] = youtube.upload(video_path, title=title, dry_run=dry_run)
    if "facebook" in config["posting"]["platforms"]:
        results["facebook"] = facebook.upload(video_path, description=title, dry_run=dry_run)
    if "instagram" in config["posting"]["platforms"]:
        # Instagram needs a public URL - see README for the GitHub Release hosting step.
        print("[INFO] Instagram posting requires a public video URL - see README.")
        results["instagram"] = {"skipped": "needs public URL, see README"}
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", default=None, help="Force a specific type id instead of random pick")
    parser.add_argument("--out", default="output.mp4")
    args = parser.parse_args()

    config = load_config()
    type_config = pick_type(config, forced_type=args.type)
    print(f"Selected type: {type_config['id']}")

    try:
        generate(type_config, config, args.out)
    except Exception as e:
        # If the AI-generation path (anime_scene) fails - most commonly a
        # Gemini quota/rate-limit exhaustion - don't let a single provider
        # outage kill the whole scheduled post. Fall back to the stock-footage
        # path instead, which has no Gemini dependency. Only do this when the
        # type was randomly picked; if the user explicitly forced a type via
        # --type, respect that and fail loudly instead of silently swapping.
        if type_config["id"] == "anime_scene" and args.type is None:
            print(f"[fallback] anime_scene failed ({e}); falling back to macro_abstract")
            type_config = next(t for t in config["types"] if t["id"] == "macro_abstract")
            print(f"Selected type: {type_config['id']} (fallback)")
            generate(type_config, config, args.out)
        else:
            raise

    print(f"Generated: {args.out}")

    results = post_everywhere(args.out, config, title=f"{type_config['label']}")
    print(results)
