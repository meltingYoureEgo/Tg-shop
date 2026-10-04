#!/data/data/com.termux/files/usr/bin/bash
# Auto-commit + push changes in Tg-shop
cd ~/Tg-shop || exit 1

WATCH_DIRS="bot app.py config.py requirements.txt .env.example"
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)

sync_once() {
    cd ~/Tg-shop || return
    if [ -z "$(git status --porcelain)" ]; then
        return
    fi
    # Add everything except ignored
    git add -A
    # Skip if .env or secrets accidentally added
    if git diff --cached --name-only | grep -qE "^\.env$|secret|token"; then
        git reset HEAD .env 2>/dev/null
    fi
    TS=$(date '+%Y-%m-%d %H:%M:%S')
    git commit -m "auto-sync: $TS" --quiet || return
    git push origin "$BRANCH" --quiet 2>&1 | tail -1
    echo "[$TS] pushed to $BRANCH"
}

echo "▶ Watching $WATCH_DIRS for changes... (Ctrl+C to stop)"
sync_once  # initial sync

inotifywait -m -r -e modify,create,delete,move \
    --exclude '(\.git/|__pycache__|\.pyc$|\.session$|\.log$|node_modules/)' \
    ~/Tg-shop 2>/dev/null | while read -r line; do
    # debounce — wait for burst of saves
    sleep 5
    sync_once
done
