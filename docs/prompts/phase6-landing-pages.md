# Agent Prompt — Phase 6: Landing + Suggestions Pages

## Setup

- **Branch:** `feature/landing-pages`
- **Working directory:** `/root/Workspace/SubTrad`
- **First steps:**
  1. Read `agents.md` and follow it
  2. Read `superpowers/using-superpowers/SKILL.md` and announce your skill
  3. Create and switch to branch `feature/landing-pages`
  4. Read `docs/subtrad-framing.md` for full product context

## Goal

Build the premium landing page (for videos >12 min) and the suggestions page (email collection). The premium page validates market demand: goal is 200 sign-ups willing to pay 12 EUR/month. The suggestions page collects user feedback and emails as leads.

## Context — What Already Exists

Phase 1-4 are merged on `main`:
- `frontend/index.html` — Main SPA (dark theme, mobile-first)
- `frontend/css/style.css` — Shared styles
- `frontend/premium.html` — Placeholder page (needs to be replaced with real content)
- `backend/main.py` — FastAPI serves frontend/ as static files, API under /api/
- `backend/routers/translate.py` — Returns duration_seconds; frontend redirects to /premium.html if >720s

The app already redirects to premium.html when video exceeds 12 minutes.

## Tech Stack

- HTML5, CSS3, vanilla JS
- Backend: FastAPI + SQLite for lead storage
- No payment processing yet — just email collection with stated price

## New/Modified Files

```
frontend/
  premium.html        — REWRITE: Premium landing page
  suggestions.html    — NEW: Suggestions + email collection
  css/
    style.css         — MODIFY: Styles for new pages
  js/
    leads.js          — NEW: Form submission for both pages
backend/
  routers/
    leads.py          — NEW: POST /api/leads endpoint
  services/
    lead_store.py     — NEW: SQLite lead storage
  tests/
    test_leads.py     — NEW
    test_lead_store.py — NEW
```

## Tasks (TDD for backend, implement for frontend)

### Task 1: Lead storage service

Create `backend/services/lead_store.py`:
- `class LeadStore` with SQLite backend
- Database file: `data/leads.db` (auto-created)
- Table schema: `leads(id INTEGER PRIMARY KEY, email TEXT NOT NULL, type TEXT NOT NULL, message TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)`
- `type` field: "premium" or "suggestion"
- Methods:
  - `save_lead(email: str, lead_type: str, message: str | None = None) -> int` — returns lead ID
  - `get_lead_count(lead_type: str) -> int` — returns count (for displaying "X people signed up")
  - `lead_exists(email: str, lead_type: str) -> bool` — prevent duplicates

Tests (`backend/tests/test_lead_store.py`):
- Test save and retrieve count
- Test duplicate prevention (same email + type returns existing, doesn't duplicate)
- Test different types are counted separately
- Test message is optional
- Use `:memory:` SQLite for tests

### Task 2: Leads API endpoint

Create `backend/routers/leads.py`:
- `POST /api/leads` — save a lead
  - Request body: `{"email": "user@example.com", "type": "premium", "message": "optional text"}`
  - Validates email format (basic regex)
  - Validates type is "premium" or "suggestion"
  - Returns: `{"status": "ok", "lead_id": 1, "total_signups": 42}`
  - If duplicate: `{"status": "already_registered", "total_signups": 42}`
- `GET /api/leads/count?type=premium` — returns signup count (public, for displaying on page)
  - Returns: `{"type": "premium", "count": 42}`

Register router in `backend/main.py`.

Tests (`backend/tests/test_leads.py`):
- Test valid premium lead submission → 201
- Test valid suggestion submission → 201
- Test invalid email → 422
- Test invalid type → 422
- Test duplicate email → 200 with "already_registered"
- Test count endpoint returns correct number

### Task 3: Premium landing page

Rewrite `frontend/premium.html`:

Content structure:
1. **Header**: SubTrad logo + nav back to home
2. **Hero section**:
   - Headline: "SubTrad Premium arrive bientot" (or English equivalent)
   - Subheadline: "Unlimited video length. Priority processing. No ads."
   - Price badge: "12 EUR/month"
3. **Social proof counter**: "X/200 people have signed up" (fetched from API)
   - Progress bar showing X/200
4. **Sign-up form**:
   - Email input
   - Submit button: "Reserve my spot"
   - Success message after submit
   - Note: "No payment required now. We'll email you when Premium launches."
5. **Features list** (what Premium will include):
   - Videos longer than 12 minutes
   - Priority processing (faster results)
   - No ads
   - Download subtitles as SRT file
6. **Footer**: Link back to SubTrad home

Style: same dark theme as main page, consistent branding.

### Task 4: Suggestions page

Create `frontend/suggestions.html`:

Content structure:
1. **Header**: SubTrad logo + nav back to home
2. **Headline**: "Help us improve SubTrad"
3. **Form**:
   - Email input (required)
   - Textarea for suggestion (required)
   - Submit button: "Send suggestion"
   - Success message after submit
4. **Footer**: Links to home, legal

Style: same dark theme.

### Task 5: Frontend JS for forms

Create `frontend/js/leads.js`:
- Handle form submission on both premium.html and suggestions.html
- POST to `/api/leads` with appropriate type
- Show success/error messages
- On premium page: fetch and display signup count on page load
- Update counter after successful signup
- Prevent double-submit (disable button during request)

### Task 6: Navigation links

Update `frontend/index.html` footer:
- Add link to `/suggestions.html`
- Ensure `/premium.html` link works

Update premium.html and suggestions.html:
- Add link back to home `/`
- Add link to each other in footer

### Task 7: Add .gitignore for data directory

Add `data/` to `.gitignore` (SQLite database files should not be committed).
Create `data/.gitkeep` so the directory exists.

### Task 8: Verification

- [ ] All backend tests pass: `cd backend && python -m pytest tests/ -v -m "not integration"`
- [ ] Server starts at `http://localhost:8010/`
- [ ] Premium page loads at `/premium.html`
- [ ] Premium signup form submits and shows success
- [ ] Signup counter displays and updates
- [ ] Duplicate email shows "already registered" message
- [ ] Suggestions page loads at `/suggestions.html`
- [ ] Suggestion form submits and shows success
- [ ] Footer links work on all 3 pages
- [ ] Pages are responsive (mobile + desktop)
- [ ] All code committed on `feature/landing-pages`
- [ ] No TODO/FIXME left
- [ ] Clean `git status`
