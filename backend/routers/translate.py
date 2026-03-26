from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from yt_dlp import YoutubeDL

try:
    from backend.config import get_settings
    from backend.models import TranslateRequest, TranslateResponse
    from backend.services.audio_extractor import cleanup_audio, extract_audio
    from backend.services.duration_checker import check_duration
    from backend.services.subtitle_fetcher import fetch_existing_subtitles
    from backend.services.transcriber import transcribe_audio
    from backend.services.url_validator import detect_platform, validate_url
    from backend.services.video_id import extract_video_id
except ModuleNotFoundError:  # pragma: no cover - runtime fallback for `uvicorn main:app`
    from config import get_settings
    from models import TranslateRequest, TranslateResponse
    from services.audio_extractor import cleanup_audio, extract_audio
    from services.duration_checker import check_duration
    from services.subtitle_fetcher import fetch_existing_subtitles
    from services.transcriber import transcribe_audio
    from services.url_validator import detect_platform, validate_url
    from services.video_id import extract_video_id


router = APIRouter(prefix="/api", tags=["translate"])
YOUTUBE_COOKIE_FILE = Path("/root/yt_cookies.txt")


def fetch_video_duration_seconds(url: str) -> int:
    options = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
    }
    if YOUTUBE_COOKIE_FILE.exists():
        options["cookiefile"] = str(YOUTUBE_COOKIE_FILE)

    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)
    return int(info.get("duration") or 0)


@router.post("/translate", response_model=TranslateResponse)
def translate_video(request: TranslateRequest) -> TranslateResponse:
    settings = get_settings()

    if not validate_url(request.url):
        raise HTTPException(status_code=400, detail="Unsupported video URL")

    if request.target_lang not in settings.supported_languages:
        raise HTTPException(status_code=400, detail="Unsupported target language")

    platform = detect_platform(request.url)
    if platform is None:
        raise HTTPException(status_code=400, detail="Unsupported video URL")

    video_id = extract_video_id(request.url, platform)
    try:
        duration_seconds = fetch_video_duration_seconds(request.url)
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={
                "detail": "Video metadata lookup failed",
                "error": str(exc),
            },
        )
    duration_result = check_duration(duration_seconds)

    if not duration_result.allowed:
        return JSONResponse(
            status_code=403,
            content={
                "detail": "Video exceeds maximum duration",
                "redirect": duration_result.redirect,
                "duration_seconds": duration_result.duration_seconds,
            },
        )

    subtitles = fetch_existing_subtitles(request.url)
    if subtitles is not None:
        return TranslateResponse(
            platform=platform,
            video_id=video_id,
            subtitles=subtitles,
            duration_seconds=duration_result.duration_seconds,
            needs_transcription=False,
            source="existing_captions",
        )

    audio_path = ""
    try:
        audio_path = extract_audio(request.url, video_id)
        transcribed_segments = transcribe_audio(audio_path, settings.openai_api_key)
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={
                "detail": "Transcription pipeline failed",
                "error": str(exc),
            },
        )
    finally:
        if audio_path:
            cleanup_audio(audio_path)

    return TranslateResponse(
        platform=platform,
        video_id=video_id,
        subtitles=transcribed_segments,
        duration_seconds=duration_result.duration_seconds,
        needs_transcription=True,
        source="whisper_transcription",
    )
