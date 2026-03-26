from urllib.parse import parse_qs, urlparse


def extract_video_id(url: str, platform: str) -> str:
    parsed_url = urlparse(url)

    if platform == "youtube":
        if parsed_url.netloc == "youtu.be":
            return parsed_url.path.strip("/").split("/")[0]

        if parsed_url.path.startswith("/watch"):
            video_id = parse_qs(parsed_url.query).get("v", [""])[0]
            if video_id:
                return video_id

        if parsed_url.path.startswith("/shorts/"):
            return parsed_url.path.strip("/").split("/")[1]

    if platform == "tiktok":
        return parsed_url.path.strip("/").split("/")[-1]

    if platform == "instagram":
        return parsed_url.path.strip("/").split("/")[-1]

    raise ValueError(f"Unsupported platform: {platform}")
