# Frontend Player Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the Phase 4 SubTrad mobile-first frontend player, serve it from FastAPI, and wire translated subtitle playback on official embeds.

**Architecture:** FastAPI serves a static vanilla-JS frontend from `frontend/` while preserving `/api/*` routes. The frontend is split into small modules for API transport, app orchestration, player abstraction, and subtitle synchronization. Backend tests protect the serving behavior; manual smoke checks cover browser interactions.

**Tech Stack:** FastAPI, pytest, HTML5, CSS3, vanilla JavaScript

---

### Task 1: Backend test coverage for frontend serving

**Files:**
- Modify: `backend/tests/test_main.py`

**Step 1: Write the failing test**

Add tests asserting:
- `GET /` returns HTML containing `SubTrad`
- `GET /css/style.css` returns CSS successfully once the frontend exists
- `GET /api/health` still returns JSON

**Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_main.py -v`
Expected: FAIL because `/` and `/css/style.css` are not served yet

**Step 3: Write minimal implementation**

Mount the frontend static directory in `backend/main.py` and add a root handler that serves `frontend/index.html`.

**Step 4: Run test to verify it passes**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_main.py -v`
Expected: PASS

### Task 2: Create the frontend shell

**Files:**
- Create: `frontend/index.html`
- Create: `frontend/css/style.css`

**Step 1: Write the frontend files**

Create semantic HTML with hidden state sections, ad placeholders, and all required containers. Add a mobile-first dark theme stylesheet with responsive layout, player aspect ratio box, subtitle overlay, loading animation, and desktop/mobile ad slot behavior.

**Step 2: Run test to verify asset path**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_main.py -v`
Expected: PASS for the CSS asset path check

### Task 3: Add API and app orchestration modules

**Files:**
- Create: `frontend/js/api.js`
- Create: `frontend/js/app.js`

**Step 1: Implement transport and state flow**

Add typed client errors in `api.js`. In `app.js`, add validation, loading state, premium notice handling, translate submission, metadata rendering, reset flow, and pre-roll placeholder flow.

**Step 2: Manual smoke check**

Run the app locally and verify empty validation, loading state, and premium redirect rendering.

### Task 4: Add player abstraction and subtitle engine

**Files:**
- Create: `frontend/js/player.js`
- Create: `frontend/js/subtitles.js`

**Step 1: Implement player wrappers**

Use the YouTube iframe API for precise timing. Use iframe embeds plus elapsed-time estimation for Instagram and TikTok. Return a unified player interface with `getCurrentTime`, `onPlay`, `onPause`, and `destroy`.

**Step 2: Implement subtitle synchronization**

Add `requestAnimationFrame` polling, segment matching, fade transitions, and teardown support.

**Step 3: Manual smoke check**

Verify subtitle overlay changes over time on a successful translation response.

### Task 5: Full verification

**Files:**
- Modify if needed: any files touched above

**Step 1: Run backend test suite**

Run: `cd backend && ../.venv/bin/python -m pytest tests/ -v -m "not integration"`
Expected: PASS

**Step 2: Run manual server smoke test**

Run: `cd backend && ../.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8010`
Expected: `/` serves the frontend and `/api/health` still responds with `{"status":"ok"}`

**Step 3: Verify repository hygiene**

Run: `git status --short`
Expected: only intended files changed before commit, then clean after commit

**Step 4: Commit**

```bash
git add backend/main.py backend/tests/test_main.py frontend docs/plans
git commit -m "feat: add frontend player"
```
