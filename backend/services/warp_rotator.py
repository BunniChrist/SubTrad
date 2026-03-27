from __future__ import annotations

import logging

import httpx


logger = logging.getLogger(__name__)
_BLOCK_PATTERNS = ["Sign in to confirm", "HTTP Error 429", "RequestBlocked"]


def is_youtube_block(exc: Exception) -> bool:
    msg = str(exc)
    return any(pattern in msg for pattern in _BLOCK_PATTERNS)


def rotate_warp_ip(rotation_url: str, timeout: float = 20.0) -> bool:
    """Call the host WARP rotation service and swallow all failures."""
    try:
        response = httpx.post(rotation_url, timeout=timeout)
        payload = response.json()
        status = payload.get("status")
        if status == "rotated":
            return True
        if status == "cooldown":
            logger.warning(
                "WARP rotation skipped due to cooldown: %s seconds remaining",
                payload.get("seconds_remaining"),
            )
            return False
        logger.warning("WARP rotation failed: %s", payload)
        return False
    except httpx.ConnectError as exc:
        logger.warning("WARP rotation service unreachable: %s", exc)
        return False
    except Exception as exc:  # pragma: no cover - defensive logging path
        logger.warning("WARP rotation failed with unexpected error: %s", exc)
        return False
