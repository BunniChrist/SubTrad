#!/bin/sh
# Decode YouTube cookies from env var if present
if [ -n "$SUBTRAD_YOUTUBE_COOKIES_B64" ]; then
  mkdir -p /root
  echo "$SUBTRAD_YOUTUBE_COOKIES_B64" | base64 -d > /root/yt_cookies.txt
  echo "YouTube cookies decoded: $(wc -c < /root/yt_cookies.txt) bytes"
else
  echo "WARNING: SUBTRAD_YOUTUBE_COOKIES_B64 not set, yt-dlp will lack cookies"
fi

echo "deno version: $(deno --version 2>&1 | head -1)"

exec uvicorn backend.main:app --host 0.0.0.0 --port 8010
