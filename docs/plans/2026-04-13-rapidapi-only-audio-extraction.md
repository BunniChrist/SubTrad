# RapidAPI-Only Audio Extraction

## Decision

SubTrad now extracts YouTube audio with exactly two RapidAPI providers:

1. `youtube-search-and-download.p.rapidapi.com`
2. `youtube-media-downloader.p.rapidapi.com`

The application keeps the public `extract_audio(url, video_id, proxy="")` signature unchanged, but the implementation is now RapidAPI-only.

## Why WARP Is Abandoned

WARP was originally kept as a low-cost path for `yt-dlp`, but it is no longer reliable enough for production use:

- YouTube consistently blocks the WARP egress IPs used from the server environment.
- IP rotation does not materially improve success rate.
- The failure mode is not occasional degradation; it is sustained anti-bot blocking.
- Retrying through WARP adds latency and operational complexity without recovering enough jobs.

In practice, WARP became a failing first hop rather than a resilience layer.

## Why yt-dlp Is Abandoned For Audio Extraction

`yt-dlp` is no longer the right primitive for the YouTube audio-download path in this deployment:

- OAuth-based mitigation is unstable in current production conditions and can fail with unsupported-login errors depending on the runtime/build.
- Cookie and cache persistence add deployment coupling and manual first-run setup.
- The extraction path became operationally fragile: proxy state, OAuth state, cache state, and YouTube anti-bot rules all had to align.
- We already validated that two RapidAPI providers return signed media URLs that are directly downloadable for our use case.

This does not mean `yt-dlp` is removed from the whole codebase. It is specifically abandoned for the YouTube audio extraction path used before Whisper transcription.

## Why These Two Providers

These two providers were the only ones validated as usable for real media retrieval in our tests:

- `youtube-search-and-download`
  - Endpoint used: `GET /video/download?id=<videoId>`
  - Returned downloadable media URLs in validation.
  - Current advertised quota observed manually: `500/day`.
- `youtube-media-downloader`
  - Endpoint used: `GET /v2/video/details?videoId=<videoId>`
  - Returned downloadable media URLs in validation.
  - Current advertised quota observed manually: `100/month`.

Other tested providers either:

- returned metadata/search data only,
- returned unusable image/storyboard URLs,
- returned signed media URLs that answered `403`,
- or failed at the documented endpoint.

## Operational Consequences

- Primary provider should be `youtube-search-and-download`.
- Secondary provider should be `youtube-media-downloader`.
- `SUBTRAD_RAPIDAPI_HOST_3` is no longer used by the application.
- Existing WARP env vars can remain in deployment config temporarily, but they are no longer part of audio extraction behavior.

## Required Environment

Use only:

```env
SUBTRAD_RAPIDAPI_KEY=...
SUBTRAD_RAPIDAPI_HOST_1=youtube-search-and-download.p.rapidapi.com
SUBTRAD_RAPIDAPI_HOST_2=youtube-media-downloader.p.rapidapi.com
```

## Scope

This decision applies to YouTube audio extraction for transcription. Other parts of the codebase may still use `yt-dlp` or WARP for non-audio paths until they are refactored separately.
