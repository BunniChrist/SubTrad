# Agent Prompt — Phase 3: LLM Translation

## Setup

- **Branch:** `feature/llm-translation`
- **Working directory:** `/root/Workspace/SubTrad`
- **First steps:**
  1. Read `agents.md` and follow it
  2. Read `superpowers/using-superpowers/SKILL.md` and announce your skill
  3. Create and switch to branch `feature/llm-translation`
  4. Read `docs/subtrad-framing.md` for full product context

## Goal

Add LLM-powered translation of subtitle segments. When the translate endpoint receives subtitles (from existing captions or Whisper transcription), translate them into the user's chosen target language using OpenAI's API. The translation must be natural, context-aware, and preserve timestamps.

## Context — What Already Exists

Phase 1 + 2 are merged on `main`. You have:
- `backend/routers/translate.py` — POST /api/translate endpoint that returns subtitles (existing or Whisper-transcribed) but **untranslated**
- `backend/services/subtitle_fetcher.py` — Fetches existing YouTube captions
- `backend/services/audio_extractor.py` — Extracts audio to temp file
- `backend/services/transcriber.py` — Whisper API transcription → `[{start, end, text}]`
- `backend/models.py` — TranslateRequest (url, target_lang), TranslateResponse (platform, video_id, subtitles, duration_seconds, needs_transcription, source)
- `backend/config.py` — Settings with `openai_api_key`, `supported_languages: ["fr", "es", "en", "ja"]`

The OpenAI API key is in `/root/SECRETS.md` under `## OpenAI`.

## Tech Stack

- OpenAI API (`openai` package, already installed) — use `gpt-4o-mini` for translation (fast, cheap, good quality)
- No new dependencies needed

## Directory Structure — New Files

```
backend/
  services/
    translator.py            — NEW: LLM-based subtitle translation
    translation_prompts.py   — NEW: prompt templates per target language
  tests/
    test_translator.py       — NEW
    test_translation_prompts.py — NEW
```

## Tasks (TDD — test first, implement, commit)

### Task 1: Translation prompt templates

Create `backend/services/translation_prompts.py` with:
- `get_translation_prompt(target_lang: str, segments: list[dict]) -> str` — builds the system + user prompt for translation
- `parse_translation_response(response_text: str, original_segments: list[dict]) -> list[dict]` — parses LLM output back into `[{start, end, text}]`

Prompt design requirements:
- System prompt: "You are a professional subtitle translator. Translate naturally, not literally. Preserve meaning, tone, and cultural context."
- Send segments in a numbered format: `1|Hello world\n2|How are you today`
- Expect response in same numbered format: `1|Bonjour le monde\n2|Comment vas-tu aujourd'hui`
- This keeps timestamps intact — just map translated text back to original segments
- Include target language name in the prompt (not just code): "French" not "fr"

Language map:
- `fr` → French
- `es` → Spanish
- `en` → English
- `ja` → Japanese

Tests (`backend/tests/test_translation_prompts.py`):
- Test prompt generation includes target language name
- Test prompt includes all segment texts in numbered format
- Test parse_translation_response correctly maps back to segments with timestamps
- Test parse handles mismatched line count gracefully (fallback to original text)
- Test empty segments returns empty list

### Task 2: Translator service

Create `backend/services/translator.py` with:
- `translate_subtitles(segments: list[dict], target_lang: str, api_key: str) -> list[dict]` — translates subtitle segments via OpenAI API

Requirements:
- Use `openai.OpenAI(api_key=api_key)` client
- Use `gpt-4o-mini` model
- **Batch segments**: send up to 20 segments per API call for context (if more than 20, split into batches)
- Each batch gets the context of surrounding segments for coherence
- Preserve `start` and `end` timestamps exactly — only `text` changes
- If source language == target language, skip translation and return as-is
- Handle API errors gracefully: if translation fails for a batch, return original untranslated text for those segments

Tests (`backend/tests/test_translator.py`):
- Test with mocked OpenAI response: verify translated text replaces original, timestamps preserved
- Test empty segments returns empty list
- Test same-language skips translation (e.g., source is "en", target is "en")
- Test batching: 50 segments should produce 3 API calls (20+20+10)
- Test API error fallback: returns original text on failure
- **One integration test** (marked `@pytest.mark.integration`): translate 3 short English segments to French with real API

### Task 3: Detect source language

Add a utility to detect the source language from subtitle segments, so we can skip translation when source == target.

Add to `backend/services/translator.py`:
- `detect_source_language(segments: list[dict]) -> str | None` — simple heuristic: send first 3 segments to OpenAI and ask "What language is this? Reply with the ISO 639-1 code only."
- Or: if Whisper already detected the language, pass it through from the transcription step

Check if the Whisper response already includes detected language. If yes, add it to the pipeline (modify TranslateResponse model to include `detected_language`). If not, use the LLM detection.

Tests:
- Test that detection returns a language code
- Test that same source/target skips translation

### Task 4: Wire translation into translate endpoint

Modify `backend/routers/translate.py`:
- After getting subtitles (from existing captions or Whisper), call `translate_subtitles(segments, target_lang, api_key)`
- Return the translated subtitles in the response
- Add `target_lang` to the response model so the frontend knows what it got
- If translation fails, still return untranslated subtitles with a warning flag

Modify `backend/models.py`:
- Add `target_lang: str` to TranslateResponse
- Add `detected_language: str | None = None` to TranslateResponse
- Add `translation_status: str = "translated"` (values: "translated", "skipped_same_lang", "failed_fallback_original")

Tests (`backend/tests/test_translate_endpoint.py`):
- Add test: valid request returns translated subtitles (mock translator)
- Add test: same source/target language returns skipped status
- Add test: translation failure returns original subtitles with warning

### Task 5: Verification

- [ ] All existing tests still pass: `python -m pytest backend/tests/ -v -m "not integration"`
- [ ] Integration test passes: `python -m pytest backend/tests/ -v -m integration`
- [ ] Server starts: `cd backend && uvicorn main:app --host 0.0.0.0 --port 8010`
- [ ] POST /api/translate with target_lang="fr" returns translated subtitles
- [ ] Response includes `target_lang`, `detected_language`, `translation_status`
- [ ] All code committed on `feature/llm-translation`
- [ ] No TODO/FIXME left
- [ ] Clean `git status`
