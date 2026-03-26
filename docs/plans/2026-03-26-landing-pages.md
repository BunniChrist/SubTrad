# Landing Pages Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the premium landing page, suggestions page, and lead capture backend for SubTrad.

**Architecture:** Add a small SQLite-backed lead store and FastAPI router under `/api/leads`, then wire two static pages to a shared browser script that submits forms and fetches premium signup counts. Keep styling inside the existing shared stylesheet so the new pages match the current product shell.

**Tech Stack:** FastAPI, SQLite, pytest, HTML5, CSS3, vanilla JavaScript

---

### Task 1: Lead storage

**Files:**
- Create: `backend/services/lead_store.py`
- Create: `backend/tests/test_lead_store.py`

**Steps:**
1. Write the failing lead store tests for save/count/duplicate/message handling.
2. Run `python -m pytest backend/tests/test_lead_store.py -v` and confirm failure.
3. Implement the minimal SQLite-backed `LeadStore`.
4. Run `python -m pytest backend/tests/test_lead_store.py -v` and confirm pass.

### Task 2: Leads API

**Files:**
- Create: `backend/routers/leads.py`
- Modify: `backend/main.py`
- Create: `backend/tests/test_leads.py`

**Steps:**
1. Write failing API tests for valid submission, duplicate handling, validation, and count endpoint.
2. Run `python -m pytest backend/tests/test_leads.py -v` and confirm failure.
3. Implement the router and register it in `backend/main.py`.
4. Run the API tests again and confirm pass.

### Task 3: Landing pages and frontend wiring

**Files:**
- Modify: `frontend/premium.html`
- Create: `frontend/suggestions.html`
- Create: `frontend/js/leads.js`
- Modify: `frontend/index.html`
- Modify: `frontend/css/style.css`
- Modify: `.gitignore`
- Create: `data/.gitkeep`

**Steps:**
1. Build the premium landing page markup with signup counter and form hooks.
2. Build the suggestions page markup with feedback form hooks.
3. Add shared JS for form submission, duplicate/success states, and count fetching.
4. Extend shared styles for the two new pages and footer links.
5. Ignore SQLite data files and create the `data/` directory placeholder.

### Task 4: Verification and cleanup

**Files:**
- Review all changed files

**Steps:**
1. Run `cd backend && python -m pytest tests/ -v -m "not integration"`.
2. Start the server and smoke test `/`, `/premium.html`, and `/suggestions.html`.
3. Check for TODO/FIXME, inspect git status, and commit the complete change set.
