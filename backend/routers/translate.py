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
    from backend.services.youtube_api import get_video_info, fetch_captions as fetch_captions_via_api
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
    from services.youtube_api import get_video_info, fetch_captions as fetch_captions_via_api


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

    # --- YouTube: use YouTube Data API v3 ---
    if platform == "youtube":
        return _handle_youtube(
            video_id=video_id,
            target_lang=request.target_lang,
            settings=settings,
            cache=cache,
            counter=counter,
        )

    # --- TikTok / Instagram: keep existing yt-dlp flow ---
    return _handle_ytdlp(
        url=request.url,
        platform=platform,
        video_id=video_id,
        target_lang=request.target_lang,
        settings=settings,
        cache=cache,
        counter=counter,
    )


def _handle_youtube(
    *,
    video_id: str,
    target_lang: str,
    settings,
    cache: SubtitleCache,
    counter: RequestCounter,
) -> TranslateResponse:
    """Handle YouTube videos via YouTube Data API v3."""
    try:
        info = get_video_info(video_id, settings.youtube_api_key)
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={
                "detail": "Video metadata lookup failed",
                "error": str(exc),
            },
        )

    if info is None:
        return JSONResponse(
            status_code=502,
            content={
                "detail": "Video metadata lookup failed",
                "error": "Video not found",
            },
        )

    duration_seconds = info["duration_seconds"]
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

    subtitles = fetch_captions_via_api(
        video_id,
        target_lang,
        settings.youtube_api_key,
        proxy=settings.warp_proxy_url or settings.proxy_url,
        cookie_file=str(YOUTUBE_COOKIE_FILE) if YOUTUBE_COOKIE_FILE.exists() else None,
    )

    if subtitles is None:
        audio_path = ""
        try:
            audio_path = extract_audio(
                f"https://www.youtube.com/watch?v={video_id}",
                video_id,
                proxy=settings.warp_proxy_url or settings.proxy_url,
            )
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
            target_lang,
            settings.openai_api_key,
            source_lang=transcription_result.get("language"),
        )

        response = build_translate_response(
            platform="youtube",
            video_id=video_id,
            subtitles=translation_result["segments"]
            if isinstance(translation_result, dict)
            else translation_result.segments,
            duration_seconds=duration_result.duration_seconds,
            needs_transcription=True,
            source="whisper_transcription",
            target_lang=target_lang,
            detected_language=translation_result["detected_language"]
            if isinstance(translation_result, dict)
            else translation_result.detected_language,
            translation_status=translation_result["translation_status"]
            if isinstance(translation_result, dict)
            else translation_result.translation_status,
        )
        counter.increment(video_id, target_lang)
        if counter.should_cache(video_id, target_lang):
            cache.store(video_id, target_lang, response.model_dump())
        return response

    translation_result = translate_subtitles_with_metadata(
        subtitles,
        target_lang,
        settings.openai_api_key,
    )

    response = build_translate_response(
        platform="youtube",
        video_id=video_id,
        subtitles=translation_result["segments"]
        if isinstance(translation_result, dict)
        else translation_result.segments,
        duration_seconds=duration_result.duration_seconds,
        needs_transcription=False,
        source="existing_captions",
        target_lang=target_lang,
        detected_language=translation_result["detected_language"]
        if isinstance(translation_result, dict)
        else translation_result.detected_language,
        translation_status=translation_result["translation_status"]
        if isinstance(translation_result, dict)
        else translation_result.translation_status,
    )
    counter.increment(video_id, target_lang)
    if counter.should_cache(video_id, target_lang):
        cache.store(video_id, target_lang, response.model_dump())
    return response


def _handle_ytdlp(
    *,
    url: str,
    platform: str,
    video_id: str,
    target_lang: str,
    settings,
    cache: SubtitleCache,
    counter: RequestCounter,
) -> TranslateResponse:
    """Handle TikTok/Instagram videos via yt-dlp (existing flow)."""
    try:
        duration_seconds = fetch_video_duration_seconds(url, proxy=settings.proxy_url)
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

    subtitles = fetch_existing_subtitles(url, proxy=settings.proxy_url)
    if subtitles is not None:
        translation_result = translate_subtitles_with_metadata(
            subtitles,
            target_lang,
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
            target_lang=target_lang,
            detected_language=translation_result["detected_language"]
            if isinstance(translation_result, dict)
            else translation_result.detected_language,
            translation_status=translation_result["translation_status"]
            if isinstance(translation_result, dict)
            else translation_result.translation_status,
        )
        counter.increment(video_id, target_lang)
        if counter.should_cache(video_id, target_lang):
            cache.store(video_id, target_lang, response.model_dump())
        return response

    audio_path = ""
    try:
        audio_path = extract_audio(url, video_id, proxy=settings.proxy_url)
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
        target_lang,
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
        target_lang=target_lang,
        detected_language=translation_result["detected_language"]
        if isinstance(translation_result, dict)
        else translation_result.detected_language,
        translation_status=translation_result["translation_status"]
        if isinstance(translation_result, dict)
        else translation_result.translation_status,
    )
    counter.increment(video_id, target_lang)
    if counter.should_cache(video_id, target_lang):
        cache.store(video_id, target_lang, response.model_dump())
    return response
