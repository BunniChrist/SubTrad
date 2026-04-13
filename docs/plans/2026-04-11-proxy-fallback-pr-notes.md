# PR Notes — Proxy Fallback (WARP -> RapidAPI)

## Required Coolify Ops After Merge

1. Add env vars in Coolify backend service:
- `SUBTRAD_RAPIDAPI_KEY`
- `SUBTRAD_RAPIDAPI_HOST_1`
- `SUBTRAD_RAPIDAPI_HOST_2`
- `SUBTRAD_RAPIDAPI_HOST_3`

2. Ensure yt-dlp cache persistence across container restarts.
- Current repo Dockerfile does not declare a persistent mount for yt-dlp cache.
- Add a Coolify volume mount for yt-dlp cache (recommended target: `/root/.cache/yt-dlp`).
- Keep existing models persistence pattern (`/app/models`) unchanged.

## First-Run OAuth2 Requirement

First yt-dlp OAuth2 use requires a manual authorization flow from the VPS console so yt-dlp can create/cache credentials.

Run an initial manual extraction once from the running container, complete the auth prompt, and verify cache files are written in the persistent yt-dlp cache volume.

## Smoke Test (Post-Merge)

1. Set `SUBTRAD_WARP_PROXY_URL=socks5h://127.0.0.1:1`.
2. Run a real YouTube translation request.
3. Confirm logs show:
- yt-dlp via WARP fails with YouTube-block pattern
- WARP rotation retry attempted
- RapidAPI fallback succeeds and returns audio path

## Known Caveat

In this environment, integration test coverage for real yt-dlp OAuth2 login is skipped when:
- yt-dlp build reports OAuth2 login unsupported, or
- filesystem is read-only for cookie/cache writes.

Unit tests cover fallback chain behavior and all RapidAPI host fallback paths.
