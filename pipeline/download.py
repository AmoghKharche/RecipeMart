"""Download Instagram Reel via yt-dlp and extract caption from metadata."""
import base64
import json
import re
import subprocess
from pathlib import Path
from typing import Tuple

import config


# Match Instagram Reel URLs
REEL_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?instagram\.com/reel/[\w\-]+",
    re.IGNORECASE,
)


def is_reel_url(text: str) -> bool:
    """Return True if text looks like an Instagram Reel URL."""
    return bool(REEL_URL_PATTERN.search(text))


# Max length for INSTAGRAM_COOKIES to be treated as a file path (avoids ENAMETOOLONG on Linux)
_MAX_COOKIE_PATH_LEN = 512


def _get_cookies_path(out_dir: Path) -> Path | None:
    """
    Resolve Instagram cookies: env can be a file path or base64-encoded content.
    Returns path to a cookies file, or None if not configured.
    """
    raw = config.INSTAGRAM_COOKIES
    if not raw:
        return None
    # Path: short string without newlines that points to an existing file (long strings are base64)
    if "\n" not in raw and len(raw) <= _MAX_COOKIE_PATH_LEN and Path(raw).exists():
        return Path(raw)
    # Base64-encoded cookies file content (for Railway / env vars)
    try:
        decoded = base64.b64decode(raw, validate=True).decode("utf-8", errors="replace")
        cookies_file = out_dir / "cookies.txt"
        cookies_file.write_text(decoded, encoding="utf-8")
        return cookies_file
    except Exception:
        return None


def fetch_caption_only(url: str, out_dir: Path) -> str:
    """
    Fetch only metadata (caption) without downloading the video. Uses yt-dlp --skip-download.
    Returns caption string. Raises RuntimeError if yt-dlp fails (e.g. login required).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(out_dir / "video.%(ext)s")
    metadata_path = out_dir / "video.info.json"
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--skip-download",
        "-o",
        output_template,
        "--write-info-json",
        "--no-warnings",
        "--quiet",
        url,
    ]
    cookies_path = _get_cookies_path(out_dir)
    if cookies_path:
        cmd.extend(["--cookies", str(cookies_path)])
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(out_dir),
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"yt-dlp failed: {result.stderr or result.stdout or 'unknown error'}"
        )
    return _extract_caption(out_dir, metadata_path)


def download_reel(url: str, out_dir: Path) -> Tuple[Path, str]:
    """
    Download reel to out_dir using yt-dlp. Return (video_path, caption).
    caption may be empty if metadata is unavailable.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    # Output template: video in out_dir with fixed name for easy lookup
    output_template = str(out_dir / "video.%(ext)s")
    # yt-dlp writes info json as video.info.json when output is video.%(ext)s
    metadata_path = out_dir / "video.info.json"

    cmd = [
        "yt-dlp",
        "--no-playlist",
        "-o",
        output_template,
        "--write-info-json",
        "--no-warnings",
        "--quiet",
        url,
    ]
    # Instagram often requires cookies to avoid "requested content not available / login required"
    cookies_path = _get_cookies_path(out_dir)
    if cookies_path:
        cmd.extend(["--cookies", str(cookies_path)])
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(out_dir),
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"yt-dlp failed: {result.stderr or result.stdout or 'unknown error'}"
        )

    # Find the downloaded video file (yt-dlp may choose extension)
    video_path = None
    for f in out_dir.iterdir():
        if f.suffix.lower() in (".mp4", ".webm", ".mkv", ".mov") and f.name.startswith("video."):
            video_path = f
            break
    if not video_path:
        # Fallback: any video file in out_dir
        for f in out_dir.iterdir():
            if f.suffix.lower() in (".mp4", ".webm", ".mkv", ".mov"):
                video_path = f
                break
        if not video_path:
            raise RuntimeError("yt-dlp did not produce a video file")

    caption = _extract_caption(out_dir, metadata_path)
    return video_path, caption


def _extract_caption(out_dir: Path, metadata_path: Path) -> str:
    """Extract caption/description from yt-dlp metadata."""
    caption = ""
    # Prefer metadata.json written by --write-info-json
    if metadata_path.exists():
        try:
            with open(metadata_path, encoding="utf-8") as fp:
                info = json.load(fp)
            caption = (
                info.get("description")
                or info.get("title")
                or info.get("fulltitle")
                or ""
            )
            if isinstance(caption, str):
                caption = caption.strip()
        except (json.JSONDecodeError, OSError):
            pass
    # Fallback: description file if yt-dlp wrote it
    if not caption:
        desc_file = out_dir / "video.description"
        if not desc_file.exists():
            for f in out_dir.glob("*.description"):
                desc_file = f
                break
        if desc_file and desc_file.exists():
            try:
                caption = desc_file.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                pass
    return caption or ""
