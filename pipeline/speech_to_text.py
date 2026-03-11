"""Speech-to-text from video using OpenAI Whisper API."""
import subprocess
from pathlib import Path

from openai import OpenAI

import config


def speech_to_text(video_path: Path) -> str:
    """
    Transcribe audio from video using OpenAI Whisper API.
    Returns full transcript text. Long videos are trimmed to STT_MAX_DURATION_SECONDS.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        return ""

    if not config.OPENAI_API_KEY:
        return ""

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    max_duration = config.STT_MAX_DURATION_SECONDS
    out_dir = video_path.parent
    file_to_send = video_path

    # Optional: trim to first N seconds if very long (Whisper has file size limits)
    trim_path = out_dir / "audio_trim.mp3"
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(video_path),
                "-t",
                str(max_duration),
                "-vn",
                "-acodec",
                "libmp3lame",
                "-q:a",
                "4",
                str(trim_path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0 and trim_path.exists():
            file_to_send = trim_path
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    try:
        with open(file_to_send, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="text",
            )
        return (transcript or "").strip()
    except Exception as e:
        raise RuntimeError(f"Whisper transcription failed: {e}") from e
