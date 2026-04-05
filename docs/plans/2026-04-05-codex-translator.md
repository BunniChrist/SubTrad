# Codex Translator Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a selectable `codex exec` translation backend without modifying the existing OpenAI translator implementation.

**Architecture:** Keep `backend/services/translator.py` and `backend/services/translation_prompts.py` unchanged. Add a new Codex-backed translator plus a dispatcher layer that routes between backends based on config and update application callers to import the dispatcher.

**Tech Stack:** Python 3, FastAPI, `subprocess.run`, pytest, monkeypatch, existing translation prompt helpers.

---

### Task 1: Add failing tests for the Codex backend

**Files:**
- Create: `backend/tests/test_translator_codex.py`
- Read: `backend/services/translator.py`
- Read: `backend/services/translation_prompts.py`

**Step 1: Write the failing tests**

Add tests for:
- `detect_source_language_codex()` returning a valid ISO code from mocked subprocess output
- `translate_subtitles_with_metadata_codex()` translating a batch and preserving timestamps
- timeout fallback to original segments
- non-zero exit fallback to original segments
- empty input returning an empty translated result
- same-language detection skipping subprocess translation

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest backend/tests/test_translator_codex.py -v`
Expected: FAIL because `backend.services.translator_codex` does not exist yet

**Step 3: Write minimal implementation**

Create `backend/services/translator_codex.py` with the smallest code necessary to satisfy the tests, reusing prompt helpers and `TranslationResult`.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest backend/tests/test_translator_codex.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/tests/test_translator_codex.py backend/services/translator_codex.py
git commit -m "feat: add codex translator backend"
```

### Task 2: Add failing tests for the dispatcher

**Files:**
- Create: `backend/tests/test_translator_dispatch.py`
- Create: `backend/services/translator_dispatch.py`
- Modify: `backend/config.py`

**Step 1: Write the failing tests**

Add tests for:
- explicit routing to the OpenAI backend
- explicit routing to the Codex backend
- default routing using `get_settings().translation_backend`

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest backend/tests/test_translator_dispatch.py -v`
Expected: FAIL because dispatcher functions and config fields do not exist yet

**Step 3: Write minimal implementation**

Add `translation_backend` and `codex_model` to settings and implement the dispatcher entrypoints mirroring the current translator API plus optional `backend` override.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest backend/tests/test_translator_dispatch.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/tests/test_translator_dispatch.py backend/services/translator_dispatch.py backend/config.py
git commit -m "feat: add translation backend dispatcher"
```

### Task 3: Rewire application callers to the dispatcher

**Files:**
- Modify: `backend/routers/translate.py`
- Read: `backend/tests/test_translate_endpoint.py`
- Read: `backend/tests/test_translate_youtube_whisper.py`
- Read: `backend/tests/test_instagram_tiktok.py`

**Step 1: Write the failing test**

Add or update the most targeted router test necessary to prove the router imports and calls the dispatcher layer instead of the OpenAI translator module directly.

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest backend/tests/test_translate_endpoint.py -v`
Expected: FAIL because the router still imports from `translator`

**Step 3: Write minimal implementation**

Update imports and call sites in the router to use `translate_subtitles_with_metadata_dispatch()` while preserving the existing request behavior.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest backend/tests/test_translate_endpoint.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/routers/translate.py backend/tests/test_translate_endpoint.py
git commit -m "feat: route translation through backend dispatcher"
```

### Task 4: Full verification

**Files:**
- Verify: `backend/services/translator.py`
- Verify: `backend/services/translation_prompts.py`
- Verify: `backend/tests/test_translator.py`

**Step 1: Run targeted regression tests**

Run: `python3 -m pytest backend/tests/test_translator.py backend/tests/test_translator_codex.py backend/tests/test_translator_dispatch.py backend/tests/test_translate_endpoint.py -v`
Expected: PASS, with integration tests skipped where appropriate

**Step 2: Run full backend test suite**

Run: `python3 -m pytest backend/tests/ -v`
Expected: PASS

**Step 3: Verify protected files are unchanged**

Run: `git diff -- backend/services/translator.py backend/services/translation_prompts.py`
Expected: no diff

**Step 4: Verify working tree state**

Run: `git status --short`
Expected: only intended tracked changes, ready for final branch handling
