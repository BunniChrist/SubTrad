# Plan: Make SubTrad Fully Functional for YouTube

**Date:** 2026-03-27
**Goal:** Reliable YouTube subtitle extraction + transcription fallback

## Current State

SubTrad has a 4-step fallback chain for YouTube, but steps 2-4 all fail because:
- YouTube timedtext API returns 0 bytes from server IP (even via WARP)
- httpx.get() on yt-dlp extracted URLs also returns 0 bytes (signed tokens need yt-dlp internal auth)
- Only yt-dlp native download actually works

## Research: Best External Projects

| Project | Role in SubTrad | Priority |
|---------|----------------|----------|
| **youtube-transcript-api** (Python) | New fast path: fetch captions without API key, no yt-dlp overhead | Phase 1 (HIGH) |
| **yt-dlp** (already in stack) | Reliable fallback via --write-sub for caption download | Phase 2 (HIGH) |
| **Whisper API** (already in stack) | Last resort: audio transcription when no captions exist | Phase 3 (HIGH) |
| yt-bulk-subtitles-downloader | Not needed — SubTrad handles one video at a time | Skip |
| transcript-create | Not needed — SubTrad already has its own Whisper pipeline | Skip |
| MCP YouTube Transcript Server | Not needed — SubTrad is self-contained | Skip |
| boul2gom/yt-dlp (Rust) | Not needed — Python stack, no performance bottleneck here | Skip |

## Phase 1: Add youtube-transcript-api as Primary Fast Path

**Branch:** `feature/youtube-transcript-api`
**Why:** This library fetches YouTube captions WITHOUT needing:
- YouTube Data API key (saves quota)
- yt-dlp (faster, lighter)
- Cookies or proxy (uses different auth method)

**What to do:**
1. `pip install youtube-transcript-api` + add to requirements.txt
2. Create new function in `youtube_api.py`:
   ```python
   from youtube_transcript_api import YouTubeTranscriptApi

   def fetch_captions_via_transcript_api(video_id: str, preferred_langs: list[str] = None) -> list[dict] | None:
       """Fast path: fetch captions via youtube-transcript-api library.
       Returns list of {text, start, duration} or None if unavailable."""
       try:
           ytt_api = YouTubeTranscriptApi()
           transcript = ytt_api.fetch(video_id, languages=preferred_langs or ["en", "fr", "es", "ja"])
           return [
               {"text": entry.text, "start": entry.start, "duration": entry.duration}
               for entry in transcript.snippets
           ]
       except Exception:
           return None
   ```
3. Insert as **Step 1** in the fallback chain (before YouTube Data API):
   ```
   NEW CHAIN:
   1. youtube-transcript-api (fast, no API key) ← NEW
   2. YouTube Data API v3 captions list (existing step 1)
   3. yt-dlp --write-sub (Phase 2)
   4. Whisper audio transcription (Phase 3)
   ```
4. Tests: mock YouTubeTranscriptApi, test success + graceful failure

**Key advantage:** This library handles YouTube's internal auth, cookie rotation, and consent pages automatically. It works from most server IPs without proxy.

## Phase 2: Fix yt-dlp Subtitle Download (existing prompt)

**Branch:** `fix/ytdlp-write-sub`
**Prompt:** `docs/prompts/fix-ytdlp-write-sub.md` (already written)

**Summary:** Replace `httpx.get(subtitle_url)` with yt-dlp native `--write-sub`:
1. Use `writesubtitles=True`, `writeautomaticsub=True`, `skip_download=True`
2. Write .srv3 files to temp dir
3. Parse with existing `parse_timedtext_xml()`
4. Clean up temp files

This becomes Step 3 in the fallback chain — heavier than youtube-transcript-api but handles edge cases (geo-restricted, age-gated with cookies).

## Phase 3: YouTube Whisper Fallback (existing prompt)

**Branch:** `feature/youtube-whisper-fallback`
**Prompt:** `docs/prompts/youtube-whisper-fallback.md` (already written)

**Summary:** When ALL caption methods fail, extract audio and transcribe:
1. `extract_audio()` → download audio via yt-dlp
2. `transcribe_audio_with_metadata()` → Whisper API
3. `translate_subtitles_with_metadata()` → GPT-4o-mini
4. Return with `source="whisper_transcription"`

This is the last resort — works for ANY video but costs OpenAI Whisper tokens.

## Phase 4: Cleanup & Hardening

**Branch:** `chore/youtube-cleanup`

1. Remove dead code:
   - `_fetch_timedtext_segments()` direct HTTP calls (always return 0 bytes)
   - `/api/debug-captions` endpoint
   - Verbose health fields
2. Update fallback chain documentation
3. Add integration test that exercises the full chain (mocked)
4. Simplify proxy logic:
   - Phase 1 (youtube-transcript-api): no proxy needed
   - Phase 2 (yt-dlp --write-sub): WARP proxy + cookies
   - Phase 3 (Whisper): WARP proxy for audio download
   - TikTok/Instagram: Bright Data proxy (unchanged)

## Final Architecture

```
User submits YouTube URL
        │
        ▼
┌─── Duration check (YouTube Data API v3) ───┐
│   > 12 min → redirect premium.html          │
│   ≤ 12 min → continue                       │
└─────────────────────────────────────────────┘
        │
        ▼
┌─── Step 1: youtube-transcript-api ──────────┐
│   Fast, no API key, no proxy                 │
│   Works for most public videos               │
│   ✓ → translate → return                     │
│   ✗ → Step 2                                 │
└─────────────────────────────────────────────┘
        │
        ▼
┌─── Step 2: YouTube Data API v3 captions ────┐
│   Lists available caption tracks             │
│   May find tracks that Step 1 missed         │
│   ✓ → translate → return                     │
│   ✗ → Step 3                                 │
└─────────────────────────────────────────────┘
        │
        ▼
┌─── Step 3: yt-dlp --write-sub ──────────────┐
│   Native download with proxy + cookies       │
│   Handles geo-restricted, age-gated          │
│   Tries manual subs + auto-generated (ASR)   │
│   ✓ → translate → return                     │
│   ✗ → Step 4                                 │
└─────────────────────────────────────────────┘
        │
        ▼
┌─── Step 4: Whisper transcription ───────────┐
│   Extract audio → Whisper API → translate    │
│   Works for ANY video with audio             │
│   Costs OpenAI tokens (last resort)          │
│   ✓ → translate → return                     │
│   ✗ → error response                         │
└─────────────────────────────────────────────┘
```

## Execution Order

| # | Phase | Prompt ready? | Estimated complexity | Dependencies |
|---|-------|--------------|---------------------|--------------|
| 1 | youtube-transcript-api | **To write** | Low (new function + insert in chain) | None |
| 2 | yt-dlp --write-sub | **Yes** (`docs/prompts/fix-ytdlp-write-sub.md`) | Medium | None (parallel with Phase 1) |
| 3 | YouTube Whisper fallback | **Yes** (`docs/prompts/youtube-whisper-fallback.md`) | Medium | Phase 2 (needs working yt-dlp for audio) |
| 4 | Cleanup | To write | Low | Phases 1-3 done |

**Phases 1 and 2 can run in parallel** (different files, different branches).
Phase 3 depends on Phase 2 (audio extraction uses yt-dlp).
Phase 4 is cleanup after everything works.

## Risk Assessment

- **youtube-transcript-api** may get rate-limited or blocked by YouTube → yt-dlp fallback covers this
- **yt-dlp** may break with YouTube updates → youtube-transcript-api covers this
- **Whisper** costs money per minute of audio → only used as last resort
- **Multiple fallbacks = resilience** — if one breaks, others still work
