# Agent Prompt — Phase 8: Legal (GDPR + Mentions Legales)

## Setup

- **Branch:** `feature/legal-pages`
- **Working directory:** `/root/Workspace/SubTrad`
- **First steps:**
  1. Read `agents.md` and follow it
  2. Read `superpowers/using-superpowers/SKILL.md` and announce your skill
  3. Create and switch to branch `feature/legal-pages`
  4. Read `docs/subtrad-framing.md` for full product context

## Goal

Add legal compliance pages (privacy policy, mentions legales) and a cookie consent banner. SubTrad uses ad cookies (Google AdSense) so GDPR requires informed consent before loading ad scripts.

## Context — What Already Exists

Phase 1-4 are merged on `main`:
- `frontend/index.html` — Main page with footer (should link to legal page)
- `frontend/css/style.css` — Dark theme styles
- `backend/main.py` — Serves frontend/ as static files
- Existing legal templates in the parent workspace: `/root/Workspace/legal/privacy-policy-fr.md` and `/root/Workspace/legal/privacy-policy-en.md` — use these as inspiration but adapt for SubTrad's specific context

## Tech Stack

- HTML5, CSS3, vanilla JS
- No dependencies

## New/Modified Files

```
frontend/
  legal.html          — NEW: Privacy policy + mentions legales
  js/
    cookies.js        — NEW: Cookie consent banner logic
  css/
    style.css         — MODIFY: Cookie banner + legal page styles
  index.html          — MODIFY: Add cookie banner + legal link in footer
```

## Tasks

### Task 1: Legal page content

Create `frontend/legal.html` with two sections:

**Section 1 — Privacy Policy (Politique de Confidentialite)**

Content to cover (write in French):
- **Identity**: SubTrad, operated by BunniChrist (individual project)
- **Data collected**: No user accounts. No personal data stored. Anonymous usage.
- **Cookies**: Advertising cookies from Google AdSense. No tracking cookies from SubTrad itself.
- **Third-party services**:
  - Google AdSense (advertising)
  - OpenAI API (transcription + translation — audio is processed temporarily and not stored)
  - YouTube/Instagram/TikTok (embedded players — subject to their own privacy policies)
- **Data retention**: No user data retained. Translated subtitles may be cached for performance (no personal data involved). Suggestion emails stored until service launch.
- **Audio processing**: Audio is extracted temporarily for transcription, then immediately deleted. No audio is stored permanently.
- **User rights**: Contact email for GDPR requests (use: contact@bunnichrist.fr as placeholder)
- **Hosting**: Hosted on Contabo VPS (Germany/EU)

**Section 2 — Mentions Legales**

Content (required by French law):
- Publisher: BunniChrist (individual)
- Contact: contact@bunnichrist.fr
- Hosting: Contabo GmbH, Aschauer Strasse 32a, 81549 Munich, Germany
- This is a personal/non-commercial project (no SIRET required for personal projects)

Style: same dark theme, readable typography, clear section headers, link back to home.

### Task 2: Cookie consent banner

Create `frontend/js/cookies.js`:

```js
const CookieConsent = {
  init(),          // Check if consent already given, show banner if not
  accept(),        // Save consent, load ad scripts
  reject(),        // Save rejection, don't load ad scripts
  hasConsent(),    // Returns true/false/null (null = not yet decided)
  reset(),         // Clear consent (for testing)
}
```

Requirements:
- Store consent in `localStorage` as `subtrad_cookie_consent` (value: "accepted", "rejected")
- Banner appears at the **bottom** of the page (fixed position)
- Banner text (in French): "SubTrad utilise des cookies publicitaires (Google AdSense) pour financer le service. Aucune donnee personnelle n'est collectee par SubTrad."
- Two buttons: "Accepter" (accent color) and "Refuser" (subtle/outline)
- On accept: hide banner, enable ad loading (set a global flag `window.subtradAdsAllowed = true`)
- On reject: hide banner, keep ads disabled (`window.subtradAdsAllowed = false`)
- If already decided (localStorage exists): don't show banner, just set the flag
- Banner should not block the page content (positioned above footer)

### Task 3: Integrate cookie consent with app

Modify `frontend/index.html`:
- Add `<script src="/js/cookies.js" defer></script>` before other scripts
- Add cookie banner HTML markup (hidden by default, shown by JS)
- Add "Manage cookies" link in footer (calls `CookieConsent.reset()` and re-shows banner)

Modify `frontend/js/app.js` (or `ads.js` if it exists):
- Check `window.subtradAdsAllowed` before showing any ad
- If ads not allowed, skip all ad placements silently (no error, just don't show)

### Task 4: Footer links on all pages

Ensure consistent footer on all pages with:
- Link to `/` (Home)
- Link to `/suggestions.html` (Suggestions) — if page exists, otherwise use `#`
- Link to `/legal.html` (Legal)
- "Manage cookies" link

Update: `frontend/index.html`, `frontend/legal.html`, `frontend/premium.html` (if exists)

### Task 5: Verification

- [ ] All backend tests still pass: `cd backend && python -m pytest tests/ -v -m "not integration"`
- [ ] Server starts at `http://localhost:8010/`
- [ ] Legal page loads at `/legal.html`
- [ ] Privacy policy section is complete and in French
- [ ] Mentions legales section is complete
- [ ] Cookie banner appears on first visit
- [ ] "Accepter" hides banner, sets consent in localStorage
- [ ] "Refuser" hides banner, blocks ads
- [ ] Refreshing page after consent: banner doesn't reappear
- [ ] "Manage cookies" link in footer re-shows the banner
- [ ] Footer links work on all pages
- [ ] All code committed on `feature/legal-pages`
- [ ] No TODO/FIXME left
- [ ] Clean `git status`
