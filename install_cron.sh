#!/bin/zsh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
BOT_SCRIPT="$PROJECT_DIR/tweet_bot.py"
LOG_FILE="$PROJECT_DIR/tweet_bot.log"
CRON_SCHEDULE="0 9 * * *"

ESCAPED_PROJECT_DIR="${PROJECT_DIR// /\\ }"
ESCAPED_PYTHON_BIN="${PYTHON_BIN// /\\ }"
ESCAPED_LOG_FILE="${LOG_FILE// /\\ }"
CRON_LINE="$CRON_SCHEDULE cd $ESCAPED_PROJECT_DIR && $ESCAPED_PYTHON_BIN tweet_bot.py >> $ESCAPED_LOG_FILE 2>&1"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing virtualenv Python at: $PYTHON_BIN" >&2
  echo "Create it first with: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi

existing_crontab="$(crontab -l 2>/dev/null || true)"
filtered_crontab="$(
  printf '%s\n' "$existing_crontab" | while IFS= read -r line; do
    [[ "$line" == *"$BOT_SCRIPT"* ]] && continue
    [[ "$line" == *"tweet_bot.py"* ]] && continue
    printf '%s\n' "$line"
  done
)"

if [[ -n "$filtered_crontab" ]]; then
  new_crontab="$(printf '%s\n%s\n' "$filtered_crontab" "$CRON_LINE")"
else
  new_crontab="$CRON_LINE"
fi

printf '%s\n' "$new_crontab" | crontab -

echo "Installed cron entry:"
echo "$CRON_LINE"
echo
echo "This machine is currently using timezone: $(date '+%Z %z')"
echo "With the system timezone set to Asia/Kolkata, this runs daily at 9:00 AM IST."
