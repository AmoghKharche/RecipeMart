"""Extract text from video frames using OpenCV + Tesseract OCR."""
from pathlib import Path
from typing import Set

import cv2
import pytesseract

import config


def extract_text_from_frames(video_path: Path) -> str:
    """
    Sample frames from video at OCR_FRAME_INTERVAL_SECONDS, run OCR on each,
    deduplicate and merge text. Skips blurry frames when possible.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        return ""

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return ""

    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    interval_frames = max(1, int(fps * config.OCR_FRAME_INTERVAL_SECONDS))
    max_frames = config.OCR_MAX_FRAMES
    seen_text: Set[str] = set()
    collected: list[str] = []
    frame_idx = 0
    read_count = 0

    try:
        while read_count < max_frames:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % interval_frames != 0:
                frame_idx += 1
                continue
            frame_idx += 1
            read_count += 1
            text = _ocr_frame(frame)
            for line in text.splitlines():
                line = line.strip()
                if line and line not in seen_text:
                    seen_text.add(line)
                    collected.append(line)
    finally:
        cap.release()

    return "\n".join(collected) if collected else ""


def _ocr_frame(frame) -> str:
    """Run Tesseract on a single BGR frame. Optional: skip if too blurry."""
    try:
        # Simple blur check: skip very blurry frames
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        if laplacian_var < 50:  # very blurry
            return ""
        return pytesseract.image_to_string(gray, lang="eng").strip()
    except Exception:
        return ""
