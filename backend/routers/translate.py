from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from yt_dlp import YoutubeDL

try:
    from backend.config import get_settings
    from backend.models import TranslateRequest, TranslateResponse
    from backend.services.audio_extractor import cleanup_audio, extract_audio
    from backend.services.cache import SubtitleCache
    from backend.services.duration_checker import check_duration
    from backend.services.request_counter import RequestCounter
    from backend.services.subtitle_fetcher import fetch_existing_subtitles
    from backend.services.transcriber import transcribe_audio_with_metadata
    from backend.services.translator import translate_subtitles_with_metadata
    from backend.services.url_validator import detect_platform, validate_url
    from backend.services.video_id import extract_video_id
except ModuleNotFoundError:  # pragma: no cover - runtime fallback for `uvicorn main:app`
    from config import get_settings
    from models import TranslateRequest, TranslateResponse
    from services.audio_extractor import cleanup_audio, extract_audio
    from services.cache import SubtitleCache
    from services.duration_checker import check_duration
    from services.request_counter import RequestCounter
    from services.subtitle_fetcher import fetch_existing_subtitles
    from services.transcriber import transcribe_audio_with_metadata
    from services.translator import translate_subtitles_with_metadata
    from services.url_validator import detect_platform, validate_url
    from services.video_id import extract_video_id


router = APIRouter(prefix="/api", tags=["translate"])
YOUTUBE_COOKIE_FILE = Path("/root/yt_cookies.txt")


def fetch_video_duration_seconds(url: str, proxy: str = "") -> int:
    options = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "ignore_no_formats_error": True,
    }
    if YOUTUBE_COOKIE_FILE.exists():
        options["cookiefile"] = str(YOUTUBE_COOKIE_FILE)
    if proxy:
        options["proxy"] = proxy

    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)
    return int(info.get("duration") or 0)


def build_translate_response(
    *,
    platform: str,
    video_id: str,
    subtitles: list[dict[str, object]],
    duration_seconds: int,
    needs_transcription: bool,
    source: str,
    target_lang: str,
    detected_language: str | None,
    translation_status: str,
) -> TranslateResponse:
    return TranslateResponse(
        platform=platform,
        video_id=video_id,
        subtitles=subtitles,
        duration_seconds=duration_seconds,
        needs_transcription=needs_transcription,
        source=source,
        target_lang=target_lang,
        detected_language=detected_language,
        translation_status=translation_status,
    )


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
    cache = SubtitleCache(settings.cache_db_path)
    counter = RequestCounter(settings.cache_db_path, threshold=settings.cache_threshold)

    cached = cache.retrieve(video_id, request.target_lang)
    if cached is not None:
        cached["translation_status"] = "cached"
        return TranslateResponse(**cached)

    try:
        duration_seconds = fetch_video_duration_seconds(request.url, proxy=settings.proxy_url)
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

    subtitles = fetch_existing_subtitles(request.url, proxy=settings.proxy_url)
    if subtitles is not None:
        translation_result = translate_subtitles_with_metadata(
            subtitles,
            request.target_lang,
            settings.openai_api_key,
        )
        response = build_translate_response(
            platform=platform,
            video_id=video_id,
            subtitles=translation_result["segments"]
            if isinstance(translation_result, dict)
            else translation_result.segments,
            duration_seconds=duration_result.duration_seconds,
            needs_transcription=False,
            source="existing_captions",
            target_lang=request.target_lang,
            detected_language=translation_result["detected_language"]
            if isinstance(translation_result, dict)
            else translation_result.detected_language,
            translation_status=translation_result["translation_status"]
            if isinstance(translation_result, dict)
            else translation_result.translation_status,
        )
        counter.increment(video_id, request.target_lang)
        if counter.should_cache(video_id, request.target_lang):
            cache.store(video_id, request.target_lang, response.model_dump())
        return response

    audio_path = ""
    try:
        audio_path = extract_audio(request.url, video_id, proxy=settings.proxy_url)
        transcription_result = transcribe_audio_with_metadata(
            audio_path,
            settings.openai_api_key,
        )
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

    translation_result = translate_subtitles_with_metadata(
        transcription_result["segments"],
        request.target_lang,
        settings.openai_api_key,
        source_lang=transcription_result.get("language"),
    )

    response = build_translate_response(
        platform=platform,
        video_id=video_id,
        subtitles=translation_result["segments"]
        if isinstance(translation_result, dict)
        else translation_result.segments,
        duration_seconds=duration_result.duration_seconds,
        needs_transcription=True,
        source="whisper_transcription",
        target_lang=request.target_lang,
        detected_language=translation_result["detected_language"]
        if isinstance(translation_result, dict)
        else translation_result.detected_language,
        translation_status=translation_result["translation_status"]
        if isinstance(translation_result, dict)
        else translation_result.translation_status,
    )
    counter.increment(video_id, request.target_lang)
    if counter.should_cache(video_id, request.target_lang):
        cache.store(video_id, request.target_lang, response.model_dump())
    return response
