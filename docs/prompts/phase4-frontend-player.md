# Agent Prompt — Phase 4: Frontend — Mobile-First Player + Subtitle Overlay

## Setup

- **Branch:** `feature/frontend-player`
- **Working directory:** `/root/Workspace/SubTrad`
- **First steps:**
  1. Read `agents.md` and follow it
  2. Read `superpowers/using-superpowers/SKILL.md` and announce your skill
  3. Create and switch to branch `feature/frontend-player`
  4. Read `docs/subtrad-framing.md` for full product context

## Goal

Build the frontend web app for SubTrad: a mobile-first, responsive single page where users paste a video URL, choose a language, and watch the video with translated subtitles overlaid on the official embedded player.

## Context — What Already Exists

Phase 1-3 are merged on `main`. The backend API is complete:

**POST /api/translate**
- Request: `{"url": "https://youtube.com/watch?v=...", "target_lang": "fr"}`
- Response:
```json
{
  "platform": "youtube",
  "video_id": "dQw4w9WgXcQ",
  "subtitles": [{"start": "0.0", "end": "3.5", "text": "Bonjour le monde"}],
  "duration_seconds": 213,
  "needs_transcription": false,
  "source": "existing_captions",
  "target_lang": "fr",
  "detected_language": "en",
  "translation_status": "translated"
}
```

**GET /api/health** — returns `{"status": "ok"}`

The backend runs on port 8010.

## Tech Stack

- HTML5, CSS3, vanilla JavaScript (NO framework — YAGNI)
- No build step, no bundler, no npm
- Served as static files by FastAPI

## Design Requirements

### Mobile-First Responsive
- Works perfectly on phone screens (320px+)
- Scales up to desktop with ad banners on sides
- Touch-friendly: large buttons, easy tap targets

### Look & Feel
- Clean, modern, minimal
- Dark theme (dark background, light text) — better for video watching
- Brand: "SubTrad" prominently displayed
- Tagline: "Understand any video, in any language."
- Color accent: pick something vibrant (agent decides)

### Layout — Main Page

**Mobile:**
```
┌──────────────────────┐
│      SubTrad         │
│  Understand any...   │
│                      │
│  [URL input field]   │
│  [Language selector] │
│  [  Translate  ]     │
│                      │
│  ┌────────────────┐  │
│  │                │  │
│  │  Video Player  │  │
│  │  (embed)       │  │
│  │                │  │
│  │  ── subtitle ──│  │
│  └────────────────┘  │
│                      │
│  [ad placeholder]    │
│                      │
│  footer: Legal | +   │
└──────────────────────┘
```

**Desktop:**
```
┌────┬──────────────────────────┬────┐
│ ad │       SubTrad            │ ad │
│    │   Understand any...      │    │
│    │                          │    │
│    │  [URL input] [Lang] [Go]│    │
│    │                          │    │
│    │  ┌──────────────────┐   │    │
│    │  │                  │   │    │
│    │  │   Video Player   │   │    │
│    │  │   (embed)        │   │    │
│    │  │                  │   │    │
│    │  │  ── subtitle ──  │   │    │
│    │  └──────────────────┘   │    │
│    │                          │    │
│    │  footer: Legal | Suggest│    │
└────┴──────────────────────────┴────┘
```

## Directory Structure — New Files

```
frontend/
  index.html          — Main page
  css/
    style.css         — All styles, mobile-first
  js/
    app.js            — Main app logic (form, state, flow)
    api.js            — Backend API client
    player.js         — Embed player manager (YouTube/Instagram/TikTok)
    subtitles.js      — Subtitle overlay rendering + sync
```

## Tasks

### Task 1: HTML structure + CSS base

Create `frontend/index.html`:
- Semantic HTML5
- Meta viewport for mobile
- Links to css/style.css and all JS files (defer)
- Structure: header (logo + tagline), form section (URL input + language selector + submit button), player section (hidden initially), loading section (hidden initially), footer (Legal | Suggestions links)
- Language selector: dropdown with French, Spanish, English, Japanese
- Ad placeholder divs: `.ad-slot-left`, `.ad-slot-right` (desktop only), `.ad-slot-bottom` (mobile)

Create `frontend/css/style.css`:
- CSS custom properties for theming (colors, spacing)
- Dark theme
- Mobile-first breakpoints (min-width: 768px for tablet, 1024px for desktop)
- Responsive player container (16:9 aspect ratio)
- Subtitle overlay positioning (absolute, bottom of player)
- Clean typography (system font stack)
- Form styling: large input, prominent button
- Animations: subtle fade-in for results

### Task 2: API client

Create `frontend/js/api.js`:
- `async function translateVideo(url, targetLang)` — POST to `/api/translate`
- Returns the parsed JSON response
- Handles errors: network error, 4xx (show message), 5xx (show message)
- Throws typed errors that `app.js` can catch and display

### Task 3: Main app logic

Create `frontend/js/app.js`:
- Form submission handler (prevent default)
- Validate input: URL not empty, language selected
- Show loading state when submitted
- Call `translateVideo()` from api.js
- On success: hide form (or shrink it), show player section, initialize player
- On error: show error message below form
- Loading state: spinner or pulsing animation with text "Generating subtitles..."
- Ad placeholder: show `.ad-interstitial` div during loading (placeholder for Phase 5)

### Task 4: YouTube embed player + subtitle sync

Create `frontend/js/player.js`:
- `function initPlayer(platform, videoId, containerElement)` — creates the embed
- YouTube: use YouTube iframe API (`https://www.youtube.com/iframe_api`)
  - Create `YT.Player` instance
  - Expose `getCurrentTime()`, `getPlayerState()`, play/pause events
- Instagram: use `https://www.instagram.com/p/{videoId}/embed/` iframe
- TikTok: use `https://www.tiktok.com/embed/v2/{videoId}` iframe
- Return a player object with a unified interface:
  ```js
  {
    getCurrentTime: () => number,  // YouTube: precise. IG/TikTok: estimated
    onPlay: (callback) => void,
    onPause: (callback) => void,
    destroy: () => void
  }
  ```
- For Instagram/TikTok (no time API): start a timer on load, estimate current time from elapsed time

Create `frontend/js/subtitles.js`:
- `function initSubtitles(subtitles, playerInterface, overlayElement)` — starts subtitle sync
- Uses `requestAnimationFrame` loop to poll `getCurrentTime()`
- Finds the current subtitle segment based on timestamp
- Updates the overlay div text
- Smooth fade transition between subtitle lines
- Clear subtitle when no segment matches current time
- `function destroySubtitles()` — stops the sync loop

### Task 5: Player section UI

Wire everything together in `app.js`:
- On successful API response:
  1. Hide or minimize the loading state
  2. Show pre-roll ad placeholder (simple overlay with "Ad" text + 5s countdown, then auto-dismiss) — actual ad code comes in Phase 5
  3. Show player container
  4. Call `initPlayer(platform, videoId, playerContainer)`
  5. Call `initSubtitles(subtitles, player, subtitleOverlay)`
- "New video" button to reset and start over
- Show metadata: detected language, translation status

### Task 6: Serve static files from FastAPI

Modify `backend/main.py`:
- Mount `frontend/` directory as static files at `/`
- Serve `index.html` at root path
- API routes stay under `/api/`
- Make sure static files don't conflict with API routes

### Task 7: Duration redirect

In `app.js`:
- If API returns `duration_seconds > 720` or a redirect signal, show a message:
  "This video is longer than 12 minutes. SubTrad Premium is coming soon!"
- With a link to the premium landing page (placeholder: `/premium.html`)

### Task 8: Verification

- [ ] Server starts and serves index.html at `http://localhost:8010/`
- [ ] Page is responsive: looks good on mobile (320px) and desktop (1920px)
- [ ] Form validates: empty URL shows error, missing language shows error
- [ ] Submit with a YouTube URL calls the API and shows loading state
- [ ] On success: YouTube player loads in embed, subtitles display and sync
- [ ] "New video" button resets the UI
- [ ] Footer links present (Legal, Suggestions — can be # hrefs for now)
- [ ] Ad placeholder divs are present but don't interfere with UX
- [ ] All backend tests still pass: `python -m pytest backend/tests/ -v -m "not integration"`
- [ ] All code committed on `feature/frontend-player`
- [ ] No TODO/FIXME left
- [ ] Clean `git status`
