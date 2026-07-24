"""
Uploader: Instagram Reels (via Graph API - requires an IG Business/Creator
account linked to a Facebook Page).

Instagram's API requires the video to be hosted at a public URL (it does not
accept raw file upload directly), so this script needs a place to host the
file temporarily. See README.md "Instagram setup" for free hosting options
(e.g. a GitHub Release asset URL, since your repo is already on GitHub).

Env vars required:
    IG_BUSINESS_ACCOUNT_ID
    IG_ACCESS_TOKEN
"""
import os
import time
import requests

GRAPH_VERSION = "v21.0"


def upload(public_video_url, caption="", dry_run=True):
    if dry_run:
        print(f"[DRY RUN] Would upload to Instagram: {public_video_url}")
        return {"dry_run": True}

    ig_id = os.environ["IG_BUSINESS_ACCOUNT_ID"]
    token = os.environ["IG_ACCESS_TOKEN"]

    # Step 1: create a media container
    create_url = f"https://graph.facebook.com/{GRAPH_VERSION}/{ig_id}/media"
    resp = requests.post(create_url, data={
        "media_type": "REELS",
        "video_url": public_video_url,
        "caption": caption,
        "access_token": token,
    })
    resp.raise_for_status()
    container_id = resp.json()["id"]

    # Step 2: poll until the container is ready
    status_url = f"https://graph.facebook.com/{GRAPH_VERSION}/{container_id}"
    for _ in range(30):
        status_resp = requests.get(status_url, params={
            "fields": "status_code", "access_token": token,
        })
        status = status_resp.json().get("status_code")
        if status == "FINISHED":
            break
        time.sleep(10)
    else:
        raise RuntimeError("Instagram media container did not finish processing in time.")

    # Step 3: publish
    publish_url = f"https://graph.facebook.com/{GRAPH_VERSION}/{ig_id}/media_publish"
    pub_resp = requests.post(publish_url, data={
        "creation_id": container_id,
        "access_token": token,
    })
    pub_resp.raise_for_status()
    return pub_resp.json()
