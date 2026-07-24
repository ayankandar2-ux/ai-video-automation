"""
Uploader: Facebook Page video (Reels)

Requires a long-lived Page access token. See README.md "Facebook/Instagram setup".

Env vars required:
    FB_PAGE_ID
    FB_PAGE_ACCESS_TOKEN
"""
import os
import requests

GRAPH_VERSION = "v21.0"


def upload(video_path, description="", dry_run=True):
    if dry_run:
        print(f"[DRY RUN] Would upload to Facebook Page: {video_path}")
        return {"dry_run": True}

    page_id = os.environ["FB_PAGE_ID"]
    token = os.environ["FB_PAGE_ACCESS_TOKEN"]
    url = f"https://graph-video.facebook.com/{GRAPH_VERSION}/{page_id}/videos"

    with open(video_path, "rb") as f:
        files = {"source": f}
        data = {"description": description, "access_token": token}
        resp = requests.post(url, files=files, data=data, timeout=300)
    resp.raise_for_status()
    return resp.json()
