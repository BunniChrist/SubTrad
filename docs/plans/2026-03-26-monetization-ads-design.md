# Monetization Ads Design

**Date:** 2026-03-26
**Branch:** `feature/monetization-ads`

## Goal

Add Phase 5 ad placements to the SubTrad frontend with placeholder inventory that matches the product framing: an interstitial during subtitle generation, a 5-second pre-roll before playback, persistent playback banners, and a pause overlay.

## Scope

- Reuse the existing SPA structure in `frontend/`
- Add explicit ad markup for all required placements
- Centralize ad lifecycle behavior in a new `frontend/js/ads.js` module
- Wire ad visibility into the translate, playback, pause, and reset flows
- Preserve subtitle readability and correct overlay layering in mobile and fullscreen contexts

## Approach

Keep all ad rendering in the DOM as placeholder slots and let a small `AdManager` control visibility and timing. This keeps `app.js` focused on product flow while `ads.js` owns interstitial transitions, pre-roll countdown state, pause overlay state, banner activation, and teardown.

The player area remains the main positioning context for pre-roll, subtitles, and the pause overlay. CSS will enforce the required stacking order so subtitles always remain above ad UI.

## UI Structure

- Loading section: fullscreen-like interstitial panel with placeholder ad unit
- Player stage: pre-roll overlay and pause overlay positioned over the player
- Desktop: left and right 160x600 banner slots visible from `1024px` upward
- Mobile: fixed 320x50 bottom banner visible below `1024px`

## Behavior

- Form submit shows the interstitial before the translate API request
- Any translate completion path hides the interstitial
- Successful translation shows player chrome, then a 5-second pre-roll before player initialization
- Active players register `onPlay` and `onPause` callbacks to toggle the pause overlay
- Reset destroys all ad state, including countdown timers and visible slots

## AdSense Preparation

`ads.js` will contain a short commented section describing the exact changes needed to swap the placeholder slots for real AdSense `<ins>` elements and initialization calls once an approved account exists.

## Testing Strategy

- Add a frontend unit test file for `AdManager` using the Node test runner and a small fake DOM
- Cover interstitial visibility, pre-roll countdown completion, pause overlay toggling, banner activation, and teardown
- Run the backend non-integration suite after the frontend changes
- Run a local server smoke test on `http://localhost:8010/` for the full user flow
