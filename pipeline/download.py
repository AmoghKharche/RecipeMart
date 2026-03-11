"""Download Instagram Reel via yt-dlp and extract caption from metadata."""
import json
import re
import subprocess
from pathlib import Path
from typing import Tuple


# Match Instagram Reel URLs
REEL_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?instagram\.com/reel/[\w\-]+",
    re.IGNORECASE,
)


def is_reel_url(text: str) -> bool:
    """Return True if text looks like an Instagram Reel URL."""
    return bool(REEL_URL_PATTERN.search(text))


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
