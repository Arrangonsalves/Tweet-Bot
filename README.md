# Daily Tweet Bot for Your SaaS

This bot generates a unique promotional tweet every day for your SaaS app, optionally creates an image, and posts it to X (Twitter).

Configured for:
- App URL: `https://auditor-ai-git-main-lucys-projects-d362fb4f.vercel.app/`
- AI text provider: OpenAI or Gemini
- Image generation: OpenAI image model (optional)

## 1) Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Then edit `.env` and add your keys:
- X API credentials
- `OPENAI_API_KEY` (if using OpenAI)
- `GEMINI_API_KEY` (if using Gemini)

## 2) Test run (no posting)

Keep `DRY_RUN=true` first, then run:

```bash
python tweet_bot.py
```

## 3) Enable posting

Set in `.env`:
- `DRY_RUN=false`

Optional image posting:
- `ENABLE_IMAGE=true`
- Ensure `OPENAI_API_KEY` and `OPENAI_IMAGE_MODEL` are set

Run:

```bash
python tweet_bot.py
```

## 4) Run in the cloud for free with GitHub Actions

The repository includes a GitHub Actions workflow at `.github/workflows/daily-post.yml`.
It runs every day at `9:00 AM IST` using GitHub Actions timezone-aware scheduling.

Before enabling it:
- Push this project to a GitHub repository
- Add these repository secrets in `Settings > Secrets and variables > Actions`:
  - `X_API_KEY`
  - `X_API_SECRET`
  - `X_ACCESS_TOKEN`
  - `X_ACCESS_TOKEN_SECRET`
  - `OPENAI_API_KEY` if using OpenAI
  - `GEMINI_API_KEY` if using Gemini
- Edit `.github/workflows/daily-post.yml` if you want to change app text, provider, image generation, or schedule

Then open the `Actions` tab in GitHub and run the workflow once with `workflow_dispatch` to test it.

Important:
- The runner is temporary, so the workflow commits `tweet_history.json` back to the repo after each run to preserve anti-repeat history
- If your repo is public, standard GitHub-hosted runners are free
- If your repo is private on GitHub Free, you get a monthly free Actions allowance that is usually more than enough for one short run per day
- In public repos, GitHub may automatically disable scheduled workflows after 60 days of no repository activity

## 5) Optional: local cron on your Mac

If you still want a local fallback schedule on your Mac, you can use:

```cron
0 9 * * * cd "/Users/arrangonsalves/Documents/Tweet bot" && "/Users/arrangonsalves/Documents/Tweet bot/.venv/bin/python" "/Users/arrangonsalves/Documents/Tweet bot/tweet_bot.py" >> "/Users/arrangonsalves/Documents/Tweet bot/tweet_bot.log" 2>&1
```

## Notes

- The bot stores prior tweets in `tweet_history.json` and uses recent history to avoid repeats.
- It retries generation up to 5 times if a near-duplicate appears.
- It auto-shortens the app URL (TinyURL) to save characters.
- If image generation is enabled while using Gemini text, the bot can still use OpenAI for image generation when OpenAI keys are present.
