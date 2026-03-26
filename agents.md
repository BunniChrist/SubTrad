# Agent Guidelines

You are a coding agent working on the SubTrad project. Read this file entirely before starting.

## Project

SubTrad is a free, anonymous web app. Users paste a video URL (YouTube, Instagram, TikTok), choose an output language, and watch the video with translated subtitles overlaid on the official embedded player.

Full product spec: `docs/subtrad-framing.md`

## Superpowers Framework

You MUST use the superpowers skills. At the start of your work:
1. Read `superpowers/using-superpowers/SKILL.md`
2. Announce which superpowers skill(s) you are using
3. Follow the skill instructions exactly

Key skills:
- `superpowers/test-driven-development/SKILL.md` — TDD is mandatory
- `superpowers/using-git-worktrees/SKILL.md` — Work in isolated worktrees
- `superpowers/verification-before-completion/SKILL.md` — Verify before declaring done
- `superpowers/finishing-a-development-branch/SKILL.md` — Clean up before merge

## Git Workflow

- Always work on the branch specified in your prompt
- Commit frequently (after each passing test)
- Commit message format: `feat: short description` or `fix: short description`
- Do NOT push to remote — the supervisor handles that

## Autonomy

You have FULL autonomy on all reversible decisions:
- Choice of library or implementation approach
- Code structure and patterns
- Test strategy details
- File naming within the specified directory

Do NOT ask questions. Make the best decision and move forward.

## TDD Cycle (mandatory)

For every piece of functionality:
1. Write the failing test FIRST
2. Run it — confirm it fails
3. Write minimal code to make it pass
4. Run it — confirm it passes
5. Commit

## Quality Standards

- DRY — Don't Repeat Yourself
- YAGNI — You Aren't Gonna Need It (no speculative features)
- Clean, readable code
- No dead code, no commented-out code
- Tests cover happy path + error cases

## Verification Before Completion

Before declaring your work done:
1. All tests pass (`python -m pytest backend/tests/ -v`)
2. Manual smoke test (describe what you tested)
3. No TODO/FIXME left behind
4. Clean git status (everything committed)
