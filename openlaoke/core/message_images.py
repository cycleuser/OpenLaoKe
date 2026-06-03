"""Message image support - extracts image references and formats for vision API."""

from __future__ import annotations

import base64
import os
import re
from pathlib import Path

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}
_IMAGE_PATTERN = re.compile(
    r"!?\[.*?\]\(([^\s)]+\.(?:png|jpg|jpeg|gif|webp|bmp|svg))\)", re.IGNORECASE
)
_FILE_REF_PATTERN = re.compile(
    r"(?:attach|image|see|view|open)\s+([^\s]+\.(?:png|jpg|jpeg|gif|webp|bmp|svg))", re.IGNORECASE
)


def extract_image_paths(message: str, workspace: str | None = None) -> list[str]:
    """Extract referenced image paths from a message.

    Detects: markdown image syntax, @file references, plain file paths.
    """
    paths: list[str] = []

    for match in _IMAGE_PATTERN.finditer(message):
        path = match.group(1)
        paths.append(_resolve(path, workspace))

    for match in _FILE_REF_PATTERN.finditer(message):
        path = match.group(1)
        resolved = _resolve(path, workspace)
        if resolved not in paths:
            paths.append(resolved)

    return [p for p in paths if p and os.path.exists(p) and _is_image(p)]


def encode_image_base64(file_path: str) -> str | None:
    """Encode an image file as base64 data URI."""
    try:
        ext = Path(file_path).suffix.lower().lstrip(".")
        mime_map = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "gif": "image/gif",
            "webp": "image/webp",
            "bmp": "image/bmp",
            "svg": "image/svg+xml",
        }
        mime = mime_map.get(ext, "image/png")
        with open(file_path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime};base64,{data}"
    except OSError:
        return None


def format_vision_message(text: str, image_paths: list[str]) -> dict:
    """Format a message for vision API with text + images."""
    content: list[dict] = [{"type": "text", "text": text}]
    for path in image_paths:
        encoded = encode_image_base64(path)
        if encoded:
            content.append({"type": "image_url", "image_url": {"url": encoded}})
    return {"role": "user", "content": content}


def model_supports_vision(model: str) -> bool:
    """Check if a model likely supports vision input."""
    vision_models = {
        "gpt-4o",
        "gpt-4-turbo",
        "gpt-4-vision",
        "claude-3",
        "claude-3.5",
        "claude-3-opus",
        "claude-sonnet",
        "claude-haiku",
        "gemini",
        "gemma3",
        "llava",
        "bakllava",
        "cogvlm",
        "qwen-vl",
        "pixtral",
        "llama3.2-vision",
    }
    return any(vm in model.lower() for vm in vision_models)


def _resolve(path: str, workspace: str | None) -> str | None:
    if os.path.isabs(path):
        return path
    if workspace:
        return os.path.normpath(os.path.join(workspace, path))
    return os.path.normpath(os.path.join(os.getcwd(), path))


def _is_image(path: str) -> bool:
    return Path(path).suffix.lower() in _IMAGE_EXTENSIONS
