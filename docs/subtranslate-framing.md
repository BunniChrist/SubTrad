# SubTranslate — Project Framing V1

## Concept

Free, anonymous web app. User pastes a video link, chooses output language, gets translated subtitles overlaid on the official embedded player.

**Tagline:** Understand any video, in any language.

## Target User

Content **consumers** (not creators). Someone who finds a video in a foreign language and just wants to understand it. Zero technical skill required.

## Supported Platforms (V1)

- YouTube
- Instagram (Reels/videos)
- TikTok

## Output Languages (V1)

- French
- Spanish
- English
- Japanese

Input language: automatic detection.

## Video Playback

- **Official embed players** (YouTube iframe, Instagram embed, TikTok embed)
- Subtitles rendered as a **synchronized overlay** on top of the embed
- No video download, no re-hosting — only audio extraction (temporary) for transcription

## Duration Limit

- **Max 12 minutes**
- Beyond 12 min: redirect to a **landing page** presenting future premium features
- Landing page goal: collect **200 sign-ups at 12 EUR/month** to validate premium launch

## User Experience

1. Paste video URL
2. Choose output language
3. **Ad during processing** (interstitial while transcription + translation runs)
4. **Pre-roll ad** before playback
5. Watch video with translated subtitles
6. Ads displayed around the player (banners)

## Monetization

| Moment | Desktop | Mobile / Fullscreen |
|---|---|---|
| During generation | Centered interstitial | Same |
| Pre-roll | Video ad before playback | Same |
| During playback | Banners around player | Subtle overlay at bottom of player |
| On pause | Banners visible | Overlay ad on paused video |

## User Account

- 100% anonymous, no account required
- Usage: single-use, no history

## Cache Strategy

- After **100 requests** for the same video+language combo, cache the translated subtitles
- Saves server costs and speeds up popular content

## Pages

1. **Main page** — URL input + language selector + player + ads
2. **Suggestions page** — Simple form with email field (lead collection)
3. **Landing page (>12 min)** — Premium pre-sale pitch, 200 sign-ups at 12 EUR/month goal
4. **Legal page** — GDPR compliance, cookie banner, privacy policy

## Technical Pipeline

1. User submits URL
2. Check cache (if popular video+lang combo exists, serve immediately)
3. Detect platform (YouTube/Instagram/TikTok)
4. Fetch existing subtitles if available (YouTube captions API, etc.)
5. If no subtitles: extract audio (temporary) → transcribe with Whisper
6. Translate via LLM (with natural, contextual quality)
7. Generate synchronized subtitle data (timestamps)
8. Render official embed player + subtitle overlay
9. Delete temporary audio files

## Stack (Recommended)

- **Frontend:** Web app, mobile-first responsive, single page
- **Backend:** Python (FastAPI) — yt-dlp, Whisper, LLM API calls are all Python-native
- **No n8n for core pipeline** (too much latency for real-time UX)
- n8n can be used for auxiliary tasks (email collection, error alerts, stats)

## Legal Approach

- Use official embed players → no ToS violation for video playback
- Audio extraction is temporary and not stored → similar to browser cache
- GDPR: cookie banner required (ad cookies), privacy policy, mentions legales
