from pydantic import BaseModel


class TranslateRequest(BaseModel):
    url: str
    target_lang: str


class SubtitleEntry(BaseModel):
    start: str
    end: str
    text: str


class TranslateResponse(BaseModel):
    platform: str
    video_id: str
    subtitles: list[SubtitleEntry | dict[str, str]]
    duration_seconds: int
    needs_transcription: bool = False
