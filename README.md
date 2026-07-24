# AI Video Automation

Generates short (10-50 sec) portrait videos on a schedule and posts them to
YouTube, Instagram, and Facebook — fully free, runs on GitHub Actions (no
generation happens on your phone).

## How it works

Each scheduled run (`.github/workflows/generate-and-post.yml`, 4x/day):
1. Picks a content "type" from `config/settings.yaml`
2. Generates a video for that type (see `scripts/generators/`)
3. Posts it to each configured platform (see `scripts/uploaders/`)

**Content types currently built:**
- `anime_scene` — AI-illustrated scenes (Gemini image gen) animated with pan/zoom + music
- `macro_abstract` — free stock footage (Pexels), trimmed + music overlay

Add more types by adding a new entry to `config/settings.yaml` and a matching
generator script in `scripts/generators/`.

## Setup

### 1. Push this to your own GitHub repo
This project was built for you but has no GitHub credentials attached. From
your device:
```bash
cd ai-video-automation
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```
Use a token you generate yourself, entered locally on your device — never
paste a token into a chat.

### 2. Add repo secrets
Go to your repo → **Settings → Secrets and variables → Actions** → add each
of these (only add the ones for platforms/types you're using):

| Secret | Where to get it |
|---|---|
| `GEMINI_API_KEY` | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) — free tier |
| `PEXELS_API_KEY` | [pexels.com/api](https://www.pexels.com/api/) — free |
| `YT_CLIENT_ID` / `YT_CLIENT_SECRET` | Google Cloud Console → enable "YouTube Data API v3" → OAuth client (Desktop app type) |
| `YT_REFRESH_TOKEN` | Generated once via OAuth consent flow using the client id/secret above (one-time manual step — see below) |
| `FB_PAGE_ID` / `FB_PAGE_ACCESS_TOKEN` | Meta for Developers → create an app → Page access token (use a long-lived token) |
| `IG_BUSINESS_ACCOUNT_ID` / `IG_ACCESS_TOKEN` | Requires an Instagram **Business/Creator** account linked to the same Facebook Page |

**Getting a YouTube refresh token (one-time, manual):** this requires a
one-time OAuth consent step in a browser since Google doesn't allow fully
non-interactive setup. Search "youtube data api get refresh token python
oauth2client quickstart" for a copy-pasteable script — run it once on your
own machine, and the refresh token it prints never expires (unless revoked).

**Instagram video hosting note:** Instagram's API requires a public URL for
the video file, not a direct upload. The simplest free option is to publish
the generated video as a GitHub Release asset first, then pass that URL to
`scripts/uploaders/instagram.py`. This step isn't wired up yet in
`run_pipeline.py` — flagged as a TODO below.

### 3. Add music
Drop a few royalty-free `.mp3` files into `assets/music/` (see
`assets/music/README.md` for free sources).

### 4. Test before going live
`config/settings.yaml` has `posting.dry_run: true` by default — runs will
generate the video and print what *would* be posted, without actually
posting. Flip to `false` once you've verified a few generated videos look
right (check the `generated-video` artifact on a manual workflow run).

## Known gaps / TODO
- [ ] Instagram: wire up GitHub Release upload → public URL → `instagram.upload()` in `run_pipeline.py`
- [ ] `anime_scene`: only 3 hardcoded themes rotate randomly — expand or make configurable
- [ ] No retry/error-alerting if a run fails (e.g. API quota hit) — consider adding a Telegram/email ping on failure, same pattern as your other bots
- [ ] Additional content "types" pending — you mentioned more reference clips to come; each needs its own generator script following the pattern in `scripts/generators/`

## Local testing (optional)
```bash
pip install -r requirements.txt
export GEMINI_API_KEY=...
python scripts/run_pipeline.py --type anime_scene --out test.mp4
```
