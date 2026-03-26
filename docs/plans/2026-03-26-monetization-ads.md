# Monetization Ads Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the Phase 5 monetization ad placements and lifecycle to the SubTrad frontend without breaking subtitle playback or reset behavior.

**Architecture:** The existing SPA keeps static placeholder ad slots in `frontend/index.html`. A new global `AdManager` module in `frontend/js/ads.js` owns visibility, timing, and cleanup for interstitial, pre-roll, banners, and pause overlays, while `frontend/js/app.js` calls into it at the required product moments.

**Tech Stack:** HTML5, CSS3, vanilla JavaScript, Node built-in test runner, FastAPI, pytest

---

### Task 1: Add failing tests for the ad lifecycle manager

**Files:**
- Create: `frontend/tests/ads.test.js`

**Step 1: Write the failing test**

Add tests asserting:
- `showInterstitial()` reveals the interstitial and `hideInterstitial()` hides it
- `showPreroll(onComplete)` updates a 5-second countdown and calls the callback after completion
- `showPauseAd()` / `hidePauseAd()` toggle the pause overlay
- `initBanners()` reveals the desktop/mobile banner slots
- `destroyAll()` clears timers and hides all ad surfaces

**Step 2: Run test to verify it fails**

Run: `cd /root/Workspace/SubTrad/.worktrees/feature-monetization-ads && node --test frontend/tests/ads.test.js`
Expected: FAIL because `frontend/js/ads.js` does not exist yet

**Step 3: Write minimal implementation**

Create `frontend/js/ads.js` with a global `window.AdManager` object that looks up the required DOM nodes, manages the countdown interval, and toggles `hidden` / `is-visible` classes.

**Step 4: Run test to verify it passes**

Run: `cd /root/Workspace/SubTrad/.worktrees/feature-monetization-ads && node --test frontend/tests/ads.test.js`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/js/ads.js frontend/tests/ads.test.js docs/plans
git commit -m "feat: add ad lifecycle manager"
```

### Task 2: Add ad markup and styling

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/css/style.css`

**Step 1: Write the failing expectation**

Use the existing ad manager tests as the red bar by requiring the DOM ids/classes they need, then add markup and CSS for:
- generation interstitial
- pre-roll overlay
- left/right desktop banners
- bottom mobile banner
- pause overlay

**Step 2: Run test to verify it still passes**

Run: `cd /root/Workspace/SubTrad/.worktrees/feature-monetization-ads && node --test frontend/tests/ads.test.js`
Expected: PASS

**Step 3: Implement minimal UI**

Update the HTML and CSS with placeholder ad surfaces, Ad labels, responsive behavior, and z-index layering so subtitles sit above pause ads and other overlays.

**Step 4: Commit**

```bash
git add frontend/index.html frontend/css/style.css
git commit -m "feat: add ad slot markup and styles"
```

### Task 3: Wire the ad manager into app flow

**Files:**
- Modify: `frontend/js/app.js`
- Modify: `frontend/index.html`

**Step 1: Extend behavior**

Call the ad manager at the required points:
- show interstitial on submit
- hide it on every API completion path
- show pre-roll before player init
- show banners once playback view is active
- bind pause/play callbacks
- destroy all ad state on reset

**Step 2: Run focused tests**

Run: `cd /root/Workspace/SubTrad/.worktrees/feature-monetization-ads && node --test frontend/tests/ads.test.js`
Expected: PASS

**Step 3: Commit**

```bash
git add frontend/js/app.js frontend/index.html
git commit -m "feat: wire ads into frontend flow"
```

### Task 4: Verify the full phase

**Files:**
- Modify if needed: any touched files above

**Step 1: Install backend dependencies if missing**

Run: `cd /root/Workspace/SubTrad/.worktrees/feature-monetization-ads/backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
Expected: toolchain available for pytest and uvicorn

**Step 2: Run backend suite**

Run: `cd /root/Workspace/SubTrad/.worktrees/feature-monetization-ads/backend && .venv/bin/python -m pytest tests/ -v -m "not integration"`
Expected: PASS

**Step 3: Run local smoke server**

Run: `cd /root/Workspace/SubTrad/.worktrees/feature-monetization-ads/backend && .venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8010`
Expected: frontend served at `http://127.0.0.1:8010/`

**Step 4: Verify repository hygiene**

Run: `git -C /root/Workspace/SubTrad/.worktrees/feature-monetization-ads status --short`
Expected: clean after final commit

**Step 5: Commit**

```bash
git add frontend docs/plans
git commit -m "feat: add monetization ad placements"
```
