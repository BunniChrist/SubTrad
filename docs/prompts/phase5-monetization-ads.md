# Agent Prompt — Phase 5: Monetization (Ads)

## Setup

- **Branch:** `feature/monetization-ads`
- **Working directory:** `/root/Workspace/SubTrad`
- **First steps:**
  1. Read `agents.md` and follow it
  2. Read `superpowers/using-superpowers/SKILL.md` and announce your skill
  3. Create and switch to branch `feature/monetization-ads`
  4. Read `docs/subtrad-framing.md` for full product context

## Goal

Integrate ad placements into SubTrad's frontend. Four ad moments: interstitial during subtitle generation, pre-roll before video playback, banners around the player, and overlay on pause. Use Google AdSense placeholders for now (real ad code requires an approved AdSense account).

## Context — What Already Exists

Phase 1-4 are merged on `main`. The frontend is a dark-theme SPA at `frontend/`:
- `frontend/index.html` — Main page with form, player section, ad placeholder divs
- `frontend/css/style.css` — Mobile-first dark theme
- `frontend/js/app.js` — Form handling, loading state, player initialization
- `frontend/js/player.js` — YouTube/IG/TikTok embed with unified interface (getCurrentTime, onPlay, onPause)
- `frontend/js/subtitles.js` — Subtitle overlay sync
- `frontend/js/api.js` — Backend API client

The app flow is: paste URL → submit → loading state → player + subtitles.

Check the existing code for `.ad-slot-*` classes and placeholder divs that may already exist.

## Tech Stack

- Vanilla JS (no framework)
- CSS for ad slot styling
- Google AdSense (placeholder mode — use `data-ad-slot` attributes with test values)

## Ad Strategy (from framing doc)

| Moment | Desktop | Mobile / Fullscreen |
|---|---|---|
| During generation | Centered interstitial | Same |
| Pre-roll | Video ad/countdown before playback | Same |
| During playback | Banners left + right of player | Subtle overlay at bottom |
| On pause | Banners visible | Overlay ad on paused video |

## New/Modified Files

```
frontend/
  js/
    ads.js            — NEW: Ad lifecycle manager
  css/
    style.css         — MODIFY: Ad slot styling
  index.html          — MODIFY: Ad slot markup
```

## Tasks

### Task 1: Ad slot markup + styling

Modify `frontend/index.html` — add ad container divs if not already present:
- `.ad-interstitial` — fullscreen overlay for during-generation ad
- `.ad-preroll` — overlay on player for pre-roll countdown
- `.ad-banner-left`, `.ad-banner-right` — side banners (desktop only, `display:none` on mobile)
- `.ad-banner-bottom` — bottom banner (mobile)
- `.ad-pause-overlay` — overlay shown when video is paused

Modify `frontend/css/style.css`:
- Style all ad containers
- Interstitial: centered, semi-transparent dark backdrop, max 728x90 or 300x250 ad unit
- Pre-roll: overlays the player, has countdown text "Video starts in Xs"
- Side banners: 160x600 (wide skyscraper) positioned left/right on desktop
- Bottom banner: 320x50 (mobile leaderboard) fixed at bottom on mobile
- Pause overlay: centered on player, appears on pause
- All ad slots should have a subtle "Ad" label and a placeholder background (light border, "Ad" text centered) so they're visible during development

### Task 2: Ad lifecycle manager

Create `frontend/js/ads.js`:

```js
const AdManager = {
  showInterstitial(),    // Show during subtitle generation
  hideInterstitial(),    // Hide when subtitles ready
  showPreroll(onComplete), // Show pre-roll, call onComplete after countdown
  showPauseAd(),         // Show overlay on video pause
  hidePauseAd(),         // Hide on resume
  initBanners(),         // Show side/bottom banners
  destroyAll(),          // Clean up on "new video"
}
```

Requirements:
- `showInterstitial()` — displays the interstitial overlay. Should have a subtle animation (fade in).
- `hideInterstitial()` — fades out and hides.
- `showPreroll(onComplete)` — shows a 5-second countdown overlay on the player. Text: "Your video starts in 5... 4... 3... 2... 1...". After countdown, calls `onComplete()` callback and hides.
- `showPauseAd()` / `hidePauseAd()` — toggle the pause overlay.
- `initBanners()` — makes side/bottom banners visible.
- `destroyAll()` — hides everything, resets state.

For now, ad content is **placeholder** (styled divs with "Ad" text). Later (with AdSense account), these divs will contain real ad scripts.

### Task 3: Wire ads into app flow

Modify `frontend/js/app.js` to integrate AdManager:

1. **On form submit** (before API call): `AdManager.showInterstitial()`
2. **On API response received**: `AdManager.hideInterstitial()`
3. **Before showing player**: `AdManager.showPreroll(() => { /* start video */ })`
4. **After player loads**: `AdManager.initBanners()`
5. **On video pause** (from player.js onPause): `AdManager.showPauseAd()`
6. **On video play** (from player.js onPlay): `AdManager.hidePauseAd()`
7. **On "new video" reset**: `AdManager.destroyAll()`

### Task 4: Fullscreen ad handling

For mobile fullscreen mode, the side banners disappear. Ensure:
- The pause overlay works in fullscreen (positioned relative to player)
- The bottom subtitle overlay doesn't conflict with ad overlays (subtitles should be ABOVE the ad overlay)
- Use `z-index` layering: player (1) < subtitles (10) < pause ad (5) — subtitles always on top

### Task 5: AdSense preparation

Add a commented-out AdSense integration section in `ads.js`:
```js
// To activate Google AdSense:
// 1. Replace placeholder divs with <ins class="adsbygoogle" ...> elements
// 2. Add <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-XXXXX"></script> to index.html
// 3. Call (adsbygoogle = window.adsbygoogle || []).push({}) after each ad slot
```

### Task 6: Verification

- [ ] All backend tests still pass: `cd backend && python -m pytest tests/ -v -m "not integration"`
- [ ] Server starts and page loads at `http://localhost:8010/`
- [ ] Interstitial appears on form submit, disappears on response
- [ ] Pre-roll countdown (5s) shows before video, then auto-dismisses
- [ ] Side banners visible on desktop (>1024px), hidden on mobile
- [ ] Bottom banner visible on mobile, hidden on desktop
- [ ] Pause overlay appears when video paused, hides on resume
- [ ] Subtitles remain readable over all ad placements
- [ ] "New video" clears all ads
- [ ] All code committed on `feature/monetization-ads`
- [ ] No TODO/FIXME left
- [ ] Clean `git status`
