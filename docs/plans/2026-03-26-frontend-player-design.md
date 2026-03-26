# Frontend Player Design

**Date:** 2026-03-26
**Branch:** `feature/frontend-player`

## Goal

Build a mobile-first single-page frontend for SubTrad where a user can submit a supported video URL, request translated subtitles, and watch the official embedded player with a synchronized subtitle overlay.

## Scope

- Serve a static frontend from FastAPI at `/`
- Keep API routes under `/api/*`
- Support YouTube, Instagram, and TikTok embeds
- Handle subtitle rendering and synchronization in vanilla JavaScript
- Surface loading, error, metadata, premium redirect, reset, and placeholder ad states

## Approach

Use a static SPA made of one HTML document, one CSS file, and four focused JavaScript modules:

- `api.js` handles `/api/translate` requests and normalizes backend errors
- `app.js` owns DOM state, validation, loading flow, premium handling, ads placeholder flow, reset flow, and orchestration
- `player.js` abstracts platform-specific embeds behind a small common interface
- `subtitles.js` polls the player clock and updates the overlay text with a fade transition

FastAPI will mount the `frontend/` directory as static files and return `index.html` for the root page. API routes remain explicit and mounted before the catch-all static behavior.

## UI Structure

- Header with `SubTrad` brand and tagline
- Form card with URL field, language selector, submit button, and inline validation/errors
- Loading section with spinner text and interstitial ad placeholder
- Premium notice state for over-limit responses
- Player section with metadata, pre-roll ad overlay, responsive embed container, subtitle overlay, and reset button
- Footer with `Legal` and `Suggestions` placeholders
- Left/right desktop ad slots and bottom mobile ad slot

## Synchronization Model

YouTube uses the iframe API for real time playback state and precise current time polling. Instagram and TikTok do not provide the same timing API in this setup, so the player wrapper will estimate playback time from elapsed wall-clock time while “playing”. The subtitle engine will use `requestAnimationFrame` to poll `getCurrentTime()` and swap visible subtitle segments based on current timestamp.

## Error Handling

- Client-side validation rejects empty URL or missing language
- API 4xx/5xx responses map to human-readable inline messages
- `403` premium redirect responses render a premium notice instead of trying to initialize the player
- Reset flow destroys subtitle polling and embedded players cleanly before showing the form again

## Testing Strategy

- Backend tests cover root page serving and static asset access without regressing `/api/health`
- Existing backend suite remains green
- Manual smoke verification covers responsive layout, submit flow, player rendering, subtitle overlay, premium redirect, and reset behavior
