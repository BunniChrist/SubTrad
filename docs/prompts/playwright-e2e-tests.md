# Agent Prompt: Playwright E2E Tests for SubTrad

## Branch

`feature/playwright-e2e`

## Context

SubTrad is a web app where users paste a video URL and get translated subtitles. The frontend is vanilla HTML/CSS/JS served from `frontend/` by FastAPI (`backend/main.py`). The site is live at `https://subtrad.bunnichrist.fr`.

Read `agents.md` before starting — follow the superpowers framework (TDD, worktrees, verification).

## Objective

Set up Playwright end-to-end tests that verify the core user journey on the live site (`https://subtrad.bunnichrist.fr`).

## Test scenarios to implement

### 1. Homepage loads correctly
- Page returns 200
- Title is present
- The URL input field is visible
- The language selector is visible
- The submit/translate button is visible

### 2. Invalid URL shows error
- Enter a non-URL string (e.g. "not a url") in the input field
- Click submit
- An error message should appear

### 3. Unsupported platform shows error
- Enter a valid URL from an unsupported platform (e.g. `https://www.example.com/video`)
- Click submit
- An error message should appear

### 4. Valid YouTube URL triggers processing
- Enter a valid YouTube URL (e.g. `https://www.youtube.com/watch?v=dQw4w9WgXcQ`)
- Select a target language
- Click submit
- The UI should show a loading/processing state (spinner, progress, or status message)
- Wait for the video player or subtitle display to appear (timeout 60s)

### 5. Navigation pages load
- `/legal.html` returns 200 and has content
- `/suggestions.html` returns 200 and has content

## Tech stack

- Use **Playwright for Python** (`playwright` + `pytest-playwright`)
- Tests go in `e2e/` at project root
- Add a `e2e/conftest.py` with the base URL config
- Add a `e2e/requirements.txt` with dependencies
- Test against the **live site**: `https://subtrad.bunnichrist.fr`

## Setup instructions to include

Add a `e2e/README.md` with:
```
pip install -r requirements.txt
playwright install chromium
pytest e2e/ -v
```

## Autonomy

You have full autonomy on all reversible decisions:
- Exact selectors to use (inspect the live site to find them)
- Test structure and helpers
- Assertion style
- Timeout values

Do NOT ask questions. Inspect the site, make the best decision, move forward.

## Verification

Before declaring done:
1. All Playwright tests pass against `https://subtrad.bunnichrist.fr`
2. Clean git status
3. No TODO/FIXME left behind
