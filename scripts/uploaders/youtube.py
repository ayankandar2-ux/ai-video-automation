"""
Uploader: YouTube (Shorts)

Requires a OAuth2 refresh token from a Google Cloud project with the
YouTube Data API v3 enabled. See README.md "YouTube setup" section.

Env vars required:
    YT_CLIENT_ID
    YT_CLIENT_SECRET
    YT_REFRESH_TOKEN
"""
import os
import requests

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos?part=snippet,status"


def get_access_token():
    resp = requests.post(TOKEN_URL, data={
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    })
    resp.raise_for_status()
    return resp.json()["access_token"]


def upload(video_path, title, description="", tags=None, dry_run=True):
    if dry_run:
        print(f"[DRY RUN] Would upload to YouTube: {video_path} | title={title}")
        return {"dry_run": True}

    access_token = get_access_token()
    metadata = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or [],
            "categoryId": "24",  # Entertainment
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }

    import json
    boundary = "-----ai_video_uploader_boundary"
    with open(video_path, "rb") as f:
        video_bytes = f.read()

    body = (
        f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{json.dumps(metadata)}\r\n"
        f"--{boundary}\r\nContent-Type: video/mp4\r\n\r\n"
    ).encode() + video_bytes + f"\r\n--{boundary}--".encode()

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": f"multipart/related; boundary={boundary}",
    }
    resp = requests.post(UPLOAD_URL, headers=headers, data=body, timeout=300)
    resp.raise_for_status()
    return resp.json()
