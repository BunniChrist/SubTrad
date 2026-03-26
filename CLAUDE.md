# SubTranslate

Free, anonymous web app for video subtitle translation.
Paste a URL (YouTube, Instagram, TikTok) → get translated subtitles on the embedded player.

## Project Structure

```
backend/          — Python FastAPI backend
docs/             — Framing, plans, agent prompts
agents.md         — Guidelines for coding agents
```

## Agent Workflow

Coding agents must read `agents.md` before starting any work.
Each phase has a prompt in `docs/prompts/`.

## Commands

- Run tests: `cd backend && python -m pytest tests/ -v`
- Start server: `cd backend && uvicorn main:app --host 0.0.0.0 --port 8010`

## Tech Stack

- Backend: Python 3.11+, FastAPI, yt-dlp, Whisper API, OpenAI API
- Frontend: HTML5, CSS3, vanilla JS (coming in Phase 4)
- Cache: SQLite
- Deployment: Coolify on subtranslate.bunnichrist.fr
