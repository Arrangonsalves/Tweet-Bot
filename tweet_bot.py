#!/usr/bin/env python3
import base64
import datetime as dt
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import requests
import tweepy
from dotenv import load_dotenv


@dataclass
class Config:
    x_api_key: str
    x_api_secret: str
    x_access_token: str
    x_access_token_secret: str

    ai_provider: str

    openai_api_key: Optional[str]
    openai_text_model: str
    openai_image_model: Optional[str]

    gemini_api_key: Optional[str]
    gemini_text_model: str

    app_name: str
    app_url: str
    app_tagline: str
    tone: str
    target_audience: str
    cta: str
    hashtags: str

    history_window: int
    history_file: str

    dry_run: bool
    enable_image: bool
    timezone: str


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def load_config() -> Config:
    load_dotenv()

    cfg = Config(
        x_api_key=os.getenv("X_API_KEY", ""),
        x_api_secret=os.getenv("X_API_SECRET", ""),
        x_access_token=os.getenv("X_ACCESS_TOKEN", ""),
        x_access_token_secret=os.getenv("X_ACCESS_TOKEN_SECRET", ""),
        ai_provider=os.getenv("AI_PROVIDER", "openai").strip().lower(),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_text_model=os.getenv("OPENAI_TEXT_MODEL", "gpt-4.1-mini"),
        openai_image_model=os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1").strip() or None,
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        gemini_text_model=os.getenv("GEMINI_TEXT_MODEL", "gemini-2.0-flash"),
        app_name=os.getenv("APP_NAME", "Your SaaS"),
        app_url=os.getenv("APP_URL", "https://example.com"),
        app_tagline=os.getenv("APP_TAGLINE", "AI tool for modern teams"),
        tone=os.getenv("TONE", "helpful, crisp, practical"),
        target_audience=os.getenv("TARGET_AUDIENCE", "SaaS teams"),
        cta=os.getenv("CTA", "Try it now"),
        hashtags=os.getenv("HASHTAGS", "#SaaS #AI"),
        history_window=int(os.getenv("HISTORY_WINDOW", "25")),
        history_file=os.getenv("HISTORY_FILE", "tweet_history.json"),
        dry_run=env_bool("DRY_RUN", True),
        enable_image=env_bool("ENABLE_IMAGE", False),
        timezone=os.getenv("TIMEZONE", "UTC"),
    )

    if cfg.ai_provider not in {"openai", "gemini"}:
        raise ValueError("AI_PROVIDER must be one of: openai, gemini")

    if cfg.ai_provider == "openai" and not cfg.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required when AI_PROVIDER=openai")
    if cfg.ai_provider == "gemini" and not cfg.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is required when AI_PROVIDER=gemini")

    return cfg


def looks_like_placeholder(value: Optional[str]) -> bool:
    if not value:
        return True
    v = value.strip().lower()
    return v.startswith("your_") or "replace_me" in v or v in {"xxx", "changeme"}


def validate_runtime_secrets(cfg: Config) -> None:
    if cfg.dry_run:
        # In dry run, allow missing X credentials, but AI key must still be valid.
        if cfg.ai_provider == "openai" and looks_like_placeholder(cfg.openai_api_key):
            raise ValueError("Set a real OPENAI_API_KEY in .env for dry run generation.")
        if cfg.ai_provider == "gemini" and looks_like_placeholder(cfg.gemini_api_key):
            raise ValueError("Set a real GEMINI_API_KEY in .env for dry run generation.")
        return

    required_x = [
        ("X_API_KEY", cfg.x_api_key),
        ("X_API_SECRET", cfg.x_api_secret),
        ("X_ACCESS_TOKEN", cfg.x_access_token),
        ("X_ACCESS_TOKEN_SECRET", cfg.x_access_token_secret),
    ]
    for name, value in required_x:
        if looks_like_placeholder(value):
            raise ValueError(f"Set a real {name} in .env before posting.")

    if cfg.ai_provider == "openai" and looks_like_placeholder(cfg.openai_api_key):
        raise ValueError("Set a real OPENAI_API_KEY in .env before posting.")
    if cfg.ai_provider == "gemini" and looks_like_placeholder(cfg.gemini_api_key):
        raise ValueError("Set a real GEMINI_API_KEY in .env before posting.")


def load_history(path: Path) -> List[dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def save_history(path: Path, items: List[dict]) -> None:
    path.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


def compact_history_for_prompt(history: List[dict], window: int) -> str:
    recent = history[-window:]
    if not recent:
        return "(none)"
    return "\n".join(f"- {item.get('text', '').strip()}" for item in recent if item.get("text"))


def make_tweet_prompt(cfg: Config, recent_tweets_bullets: str) -> str:
    today = dt.datetime.now().strftime("%Y-%m-%d")
    return f"""
You are a social media copywriter for a SaaS product.

Date: {today}
Timezone label: {cfg.timezone}
Product: {cfg.app_name}
URL: {cfg.app_url}
Tagline: {cfg.app_tagline}
Audience: {cfg.target_audience}
Tone: {cfg.tone}
CTA: {cfg.cta}
Preferred hashtags: {cfg.hashtags}

Recent tweets to avoid repeating in wording/angle:
{recent_tweets_bullets}

Write exactly ONE tweet for X that:
1) Is <= 260 characters.
2) Is specific and valuable (tip, outcome, or pain-point driven).
3) Includes the product URL.
4) Uses at most 2 hashtags.
5) Is meaningfully different from recent tweets in both phrasing and angle.
6) No emojis.

Return only the tweet text, no quotes, no extra commentary.
""".strip()


def generate_tweet_openai(cfg: Config, prompt: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=cfg.openai_api_key)
    response = client.responses.create(
        model=cfg.openai_text_model,
        input=prompt,
        temperature=0.9,
    )
    tweet = (response.output_text or "").strip()
    return tweet


def generate_tweet_gemini(cfg: Config, prompt: str) -> str:
    from google import genai

    client = genai.Client(api_key=cfg.gemini_api_key)
    response = client.models.generate_content(
        model=cfg.gemini_text_model,
        contents=prompt,
    )
    tweet = (response.text or "").strip()
    return tweet


def clean_and_validate_tweet(tweet: str) -> str:
    tweet = tweet.strip().strip('"').strip("'")
    tweet = " ".join(tweet.split())
    if not tweet:
        raise ValueError("Generated tweet is empty")
    if len(tweet) > 280:
        raise ValueError(f"Generated tweet is too long ({len(tweet)} chars)")
    return tweet


def generate_image_openai(cfg: Config, tweet_text: str) -> Optional[Path]:
    if not cfg.openai_api_key or not cfg.openai_image_model:
        return None

    from openai import OpenAI

    client = OpenAI(api_key=cfg.openai_api_key)
    prompt = (
        f"Create a clean, modern promotional image for {cfg.app_name}, a SaaS app. "
        f"Visual theme based on: {cfg.app_tagline}. "
        f"Use this campaign message as context: {tweet_text}. "
        "No logos, no copyrighted brands, no text-heavy design."
    )

    result = client.images.generate(
        model=cfg.openai_image_model,
        prompt=prompt,
        size="1024x1024",
    )

    b64_data = result.data[0].b64_json
    image_bytes = base64.b64decode(b64_data)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    tmp.write(image_bytes)
    tmp.flush()
    tmp.close()
    return Path(tmp.name)


def post_to_x(cfg: Config, tweet_text: str, image_path: Optional[Path] = None) -> str:
    auth = tweepy.OAuth1UserHandler(
        cfg.x_api_key,
        cfg.x_api_secret,
        cfg.x_access_token,
        cfg.x_access_token_secret,
    )
    api_v1 = tweepy.API(auth)

    client_v2 = tweepy.Client(
        consumer_key=cfg.x_api_key,
        consumer_secret=cfg.x_api_secret,
        access_token=cfg.x_access_token,
        access_token_secret=cfg.x_access_token_secret,
    )

    media_ids = None
    if image_path:
        media = api_v1.media_upload(filename=str(image_path))
        media_ids = [media.media_id_string]

    response = client_v2.create_tweet(text=tweet_text, media_ids=media_ids)
    tweet_id = response.data.get("id")
    if not tweet_id:
        raise RuntimeError("X API did not return tweet ID")
    return str(tweet_id)


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def is_near_duplicate(text: str, history: List[dict]) -> bool:
    normalized = " ".join(text.lower().split())
    recent_texts = [" ".join((item.get("text", "").lower().split())) for item in history[-50:]]
    return normalized in set(recent_texts)


def generate_tweet(cfg: Config, history: List[dict]) -> str:
    recent = compact_history_for_prompt(history, cfg.history_window)

    for _ in range(5):
        prompt = make_tweet_prompt(cfg, recent)
        if cfg.ai_provider == "openai":
            candidate = generate_tweet_openai(cfg, prompt)
        else:
            candidate = generate_tweet_gemini(cfg, prompt)

        tweet = clean_and_validate_tweet(candidate)
        if not is_near_duplicate(tweet, history):
            return tweet

    raise RuntimeError("Failed to generate a sufficiently new tweet after 5 attempts")


def shorten_url(url: str, timeout: int = 10) -> str:
    # Optional convenience to save characters. If unavailable, use original URL.
    endpoint = "https://tinyurl.com/api-create.php"
    try:
        r = requests.get(endpoint, params={"url": url}, timeout=timeout)
        if r.status_code == 200 and r.text.startswith("http"):
            return r.text.strip()
    except requests.RequestException:
        pass
    return url


def main() -> None:
    cfg = load_config()
    validate_runtime_secrets(cfg)
    history_path = Path(cfg.history_file)
    history = load_history(history_path)

    cfg.app_url = shorten_url(cfg.app_url)

    tweet = generate_tweet(cfg, history)
    image_path = None

    if cfg.enable_image:
        if cfg.ai_provider == "openai":
            image_path = generate_image_openai(cfg, tweet)
        elif cfg.openai_api_key and cfg.openai_image_model:
            # Gemini for text + OpenAI for image if keys exist.
            image_path = generate_image_openai(cfg, tweet)

    if cfg.dry_run:
        print("DRY_RUN=true, not posting to X")
        print("Generated tweet:")
        print(tweet)
        tweet_id = None
    else:
        tweet_id = post_to_x(cfg, tweet, image_path=image_path)
        print(f"Posted tweet ID: {tweet_id}")

    history.append(
        {
            "timestamp_utc": dt.datetime.utcnow().isoformat() + "Z",
            "tweet_id": tweet_id,
            "text": tweet,
            "hash": hash_text(tweet),
            "image_attached": bool(image_path),
            "provider": cfg.ai_provider,
        }
    )
    save_history(history_path, history)

    if image_path and image_path.exists():
        image_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
