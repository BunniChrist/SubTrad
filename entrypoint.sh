#!/bin/sh
# Decode YouTube cookies from env var if present
if [ -n "$SUBTRAD_YOUTUBE_COOKIES_B64" ]; then
  echo "$SUBTRAD_YOUTUBE_COOKIES_B64" | base64 -d > /root/yt_cookies.txt
fi

exec uvicorn backend.main:app --host 0.0.0.0 --port 8010
