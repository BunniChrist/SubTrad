# Agent Prompt: Migrate from OpenAI Whisper API to local Distil-Whisper (CPU)

## Branch

`feature/distil-whisper-local`

## Before You Start

1. Read `agents.md` and follow all instructions
2. Read `superpowers/using-superpowers/SKILL.md`
3. Announce which superpowers skill(s) you are using
4. You have FULL autonomy on all reversible decisions

## Context

SubTrad currently uses the OpenAI Whisper API (`whisper-1`) for audio transcription. This costs money per request. We are migrating to a **local Distil-Whisper model running on CPU** to eliminate API costs.

The VPS has 24 GB RAM, no GPU. CPU-only inference is required.

## Goal

Replace the OpenAI Whisper API call in `backend/services/transcriber.py` with a local Distil-Whisper model using `faster-whisper` (CTranslate2 backend, optimized for CPU).

## Technical Decisions (already made)

- **Library**: `faster-whisper` (NOT `transformers` + `torch` — too heavy for CPU)
- **Model**: `distil-large-v3` via faster-whisper (CTranslate2 format)
- **Compute**: `cpu` with `int8` quantization for speed and low memory usage
- **Model loading**: Singleton pattern — load the model ONCE at startup, reuse for all requests

## What to Change

### 1. `backend/requirements.txt`

- Add `faster-whisper>=1.1.0`
- `openai` must STAY (still used for GPT-4o-mini translation)

### 2. `backend/services/transcriber.py`

Replace the OpenAI Whisper API call with faster-whisper local inference.

**Current signature:**
```python
def transcribe_audio_with_metadata(audio_path: str, api_key: str) -> dict
def transcribe_audio(audio_path: str, api_key: str) -> list
```

**New signature** (remove `api_key` param — no longer needed for transcription):
```python
def transcribe_audio_with_metadata(audio_path: str) -> dict
def transcribe_audio(audio_path: str) -> list
```

**Expected output format must stay identical:**
```python
{
    "segments": [{"start": float, "end": float, "text": str}, ...],
    "language": str | None
}
```

**Model singleton pattern:**
```python
from faster_whisper import WhisperModel

_model = None

def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel("distil-large-v3", device="cpu", compute_type="int8")
    return _model
```

### 3. `backend/config.py`

- Add optional setting: `whisper_model: str = "distil-large-v3"`
- Remove `openai_api_key` from being required for transcription (keep it for translation)

### 4. Callers of transcriber functions

Find ALL callers of `transcribe_audio_with_metadata()` and `transcribe_audio()` in the codebase and remove the `api_key` argument. Main caller is in `backend/routers/translate.py`.

### 5. `Dockerfile`

No changes needed — `faster-whisper` only needs Python and works on CPU. The model will auto-download on first use.

### 6. Tests

- Update ALL existing transcriber tests to remove `api_key` parameter
- Add new tests:
  - Model singleton returns same instance
  - Transcription output format is correct (mock the WhisperModel)
  - Empty/missing file still returns `{"segments": [], "language": None}`
  - Invalid audio file still raises ValueError

## What NOT to Do

- Do NOT remove `openai` from requirements (still needed for translation)
- Do NOT change the translation service
- Do NOT add GPU support or CUDA dependencies
- Do NOT pre-download the model in Docker build (it will download on first run, that's fine for now)
- Do NOT change the API endpoints or response format

## Verification

1. All tests pass: `cd backend && python -m pytest tests/ -v`
2. The transcriber output format is identical to before
3. No reference to OpenAI Whisper API remains in transcriber.py
4. `openai` import only remains where used for translation
