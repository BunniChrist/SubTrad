from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from backend.routers.leads import router as leads_router
    from backend.routers.translate import router as translate_router
except ModuleNotFoundError:  # pragma: no cover - runtime fallback for `uvicorn main:app`
    from routers.leads import router as leads_router
    from routers.translate import router as translate_router


app = FastAPI(title="SubTrad Backend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check() -> dict:
    try:
        from config import get_settings
    except ModuleNotFoundError:
        from backend.config import get_settings
    s = get_settings()
    import os, subprocess, shutil
    deno_path = shutil.which("deno")
    try:
        deno_ver = subprocess.check_output(["deno", "--version"], timeout=5, stderr=subprocess.STDOUT).decode().split("\n")[0] if deno_path else "not installed"
    except Exception as e:
        deno_ver = f"error: {e}"
    return {
        "status": "ok",
        "version": os.environ.get("GIT_COMMIT_SHA") or os.environ.get("SOURCE_COMMIT", "unknown"),
        "deno": deno_ver,
        "cookie_file": os.path.exists("/root/yt_cookies.txt"),
        "cookie_size": os.path.getsize("/root/yt_cookies.txt") if os.path.exists("/root/yt_cookies.txt") else 0,
    }


app.include_router(translate_router)
app.include_router(leads_router)


@app.get("/api/debug-captions/{video_id}")
def debug_captions(video_id: str) -> dict:
    """Temporary debug endpoint — remove after fixing ASR."""
    import os, traceback
    try:
        from backend.config import get_settings
    except ModuleNotFoundError:
        from config import get_settings
    s = get_settings()
    cookie_file = "/root/yt_cookies.txt" if os.path.exists("/root/yt_cookies.txt") else None
    results = {}

    # Step 1: captions.list
    try:
        import httpx
        r = httpx.get("https://www.googleapis.com/youtube/v3/captions",
                       params={"part": "snippet", "videoId": video_id, "key": s.youtube_api_key}, timeout=10)
        tracks = r.json().get("items", [])
        results["captions_list"] = [{"lang": t["snippet"]["language"], "kind": t["snippet"]["trackKind"]} for t in tracks]
    except Exception as e:
        results["captions_list_error"] = str(e)

    # Step 2: timedtext ASR
    try:
        for lang in ["en", "fr"]:
            r = httpx.get("https://www.youtube.com/api/timedtext",
                           params={"v": video_id, "lang": lang, "kind": "asr", "fmt": "srv3"}, timeout=10)
            results[f"timedtext_asr_{lang}"] = {"status": r.status_code, "size": len(r.text)}
    except Exception as e:
        results["timedtext_error"] = str(e)

    # Step 3: yt-dlp (no proxy)
    try:
        from yt_dlp import YoutubeDL
        opts = {"skip_download": True, "writesubtitles": True, "writeautomaticsub": True,
                "quiet": True, "no_warnings": True, "ignore_no_formats_error": True}
        if cookie_file:
            opts["cookiefile"] = cookie_file
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
        auto = info.get("automatic_captions") or {}
        subs = info.get("subtitles") or {}
        results["ytdlp_auto_langs"] = len(auto)
        results["ytdlp_manual_langs"] = list(subs.keys())
    except Exception as e:
        results["ytdlp_error"] = traceback.format_exc()[-500:]

    # Step 4: yt-dlp with proxy
    try:
        opts2 = {"skip_download": True, "writesubtitles": True, "writeautomaticsub": True,
                 "quiet": True, "no_warnings": True, "ignore_no_formats_error": True}
        if cookie_file:
            opts2["cookiefile"] = cookie_file
        if s.proxy_url:
            opts2["proxy"] = s.proxy_url
        with YoutubeDL(opts2) as ydl:
            info2 = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
        auto2 = info2.get("automatic_captions") or {}
        results["ytdlp_proxy_auto_langs"] = len(auto2)
    except Exception as e:
        results["ytdlp_proxy_error"] = traceback.format_exc()[-500:]

    return results
