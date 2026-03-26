# Legal Pages Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a French legal page, GDPR cookie consent banner, and consent-aware ad behavior across SubTrad pages.

**Architecture:** Keep the implementation static and dependency-free. Add a standalone `cookies.js` module that owns consent state in `localStorage`, updates a shared `window.subtradAdsAllowed` flag, and controls a banner injected in page markup. Extend the existing shared stylesheet and update page footers for consistent legal navigation.

**Tech Stack:** HTML5, CSS3, vanilla JavaScript, FastAPI static serving, Node built-in test runner, pytest

---

### Task 1: Add failing verification for new legal assets

**Files:**
- Modify: `backend/tests/test_main.py`
- Create: `frontend/tests/cookies.test.js`

**Step 1: Write the failing tests**

- Add a backend test asserting `/legal.html` returns HTML and contains the legal page title.
- Add Node tests asserting `CookieConsent` returns `null` before choice, persists accept/reject state, sets `window.subtradAdsAllowed`, and re-shows the banner on reset.

**Step 2: Run tests to verify they fail**

Run: `cd /root/Workspace/SubTrad && python3 -m pytest backend/tests/test_main.py -v`
Expected: FAIL because `/legal.html` does not exist yet.

Run: `cd /root/Workspace/SubTrad && node --test frontend/tests/cookies.test.js`
Expected: FAIL because `frontend/js/cookies.js` does not exist yet.

### Task 2: Implement legal page and cookie consent module

**Files:**
- Create: `frontend/legal.html`
- Create: `frontend/js/cookies.js`
- Modify: `frontend/css/style.css`

**Step 1: Write minimal implementation**

- Build `legal.html` with French privacy and legal notice sections, a return link, shared footer, cookie banner markup, and script includes.
- Implement `CookieConsent.init()`, `accept()`, `reject()`, `hasConsent()`, and `reset()` around `localStorage`.
- Add shared styles for the legal layout, footer links, cookie banner, and button variants.

**Step 2: Run tests to verify they pass**

Run: `cd /root/Workspace/SubTrad && python3 -m pytest backend/tests/test_main.py -v`
Expected: PASS

Run: `cd /root/Workspace/SubTrad && node --test frontend/tests/cookies.test.js`
Expected: PASS

### Task 3: Integrate consent-aware ads and shared footer links

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/premium.html`
- Modify: `frontend/suggestions.html`
- Modify: `frontend/js/app.js`

**Step 1: Write the failing integration expectation**

- Extend the Node cookie tests if needed to verify banner visibility toggles through the public API.

**Step 2: Write minimal implementation**

- Load `cookies.js` before `app.js` where needed.
- Add cookie banner markup to `index.html`, plus “Manage cookies” links to all page footers.
- Gate ad placeholders and preroll UI in `app.js` behind `window.subtradAdsAllowed`.
- Align footers on `index.html`, `legal.html`, and `premium.html`; keep `suggestions.html` consistent as well.

**Step 3: Run targeted verification**

Run: `cd /root/Workspace/SubTrad && node --test frontend/tests/cookies.test.js`
Expected: PASS

### Task 4: Full verification

**Files:**
- No code changes required

**Step 1: Run backend tests**

Run: `cd /root/Workspace/SubTrad/backend && python3 -m pytest tests/ -v -m "not integration"`
Expected: PASS

**Step 2: Run frontend cookie tests**

Run: `cd /root/Workspace/SubTrad && node --test frontend/tests/cookies.test.js`
Expected: PASS

**Step 3: Smoke test the server**

Run: `cd /root/Workspace/SubTrad/backend && python3 -m uvicorn main:app --host 127.0.0.1 --port 8010`
Expected: server starts and serves `/`, `/legal.html`, and updated footers.
