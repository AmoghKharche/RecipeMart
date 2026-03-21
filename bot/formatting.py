"""Format recipe text for Telegram (HTML). Only text is sent — no video or media."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pipeline.recipe_schema import Recipe


def _fmt_quantity(amount: float) -> str:
    """Format scaled amount for display (compact, kitchen-friendly)."""
    rounded = round(amount, 2)
    if abs(rounded - round(rounded)) < 1e-9:
        return str(int(round(rounded)))
    s = f"{rounded:.2f}".rstrip("0").rstrip(".")
    return s


def format_structured_recipe(
    recipe: Recipe,
    scale_factor: float = 1.0,
    *,
    preamble: str | None = None,
) -> str:
    """
    Build markdown-style recipe text from structured data; optional scale on numeric amounts.
    Pass through format_recipe_for_telegram for HTML.
    """
    lines: list[str] = []
    if preamble:
        lines.append(preamble)
        lines.append("")
    title = (recipe.title or "Recipe").strip() or "Recipe"
    lines.append(f"**{title}**")
    lines.append("")
    lines.append("**Ingredients**")
    for ing in recipe.ingredients:
        if ing.amount is not None and ing.unit:
            scaled = ing.amount * scale_factor
            qty = _fmt_quantity(scaled)
            unit = ing.unit
            if unit in ("g", "ml"):
                line = f"• {qty}{unit} {ing.name}"
            else:
                line = f"• {qty} {ing.name}"
            if ing.note:
                line += f" ({ing.note})"
            lines.append(line)
        else:
            extra = f" ({ing.note})" if ing.note else ""
            lines.append(f"• {ing.name}{extra}")
    lines.append("")
    lines.append("**Steps**")
    for i, step in enumerate(recipe.steps, start=1):
        lines.append(f"{i}. {step}")
    return "\n".join(lines)


def _escape_html(s: str) -> str:
    """Escape <, >, & for Telegram HTML."""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def format_recipe_for_telegram(recipe: str) -> str:
    """
    Convert markdown-style recipe to Telegram HTML for clearer structure.
    Result: bold section headers, clean lists. No video or media — text only.
    """
    if not recipe or not recipe.strip():
        return recipe
    text = recipe.strip()
    # Escape first so we don't double-escape our own tags
    text = _escape_html(text)
    # Bold markdown **...**
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    # Headers ## or ### -> bold + newline
    text = re.sub(r"^#{1,3}\s*(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)
    # Single *italic* -> <i> (optional, keep simple)
    text = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", text)
    # Bullet lines: ensure they start with • for consistency
    lines = text.split("\n")
    out = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            out.append("")
            continue
        # Normalize bullet: "- item" or "* item" -> "• item"
        if re.match(r"^[\-\*]\s+", stripped) or re.match(r"^[\u2022\u2023\u25E6]\s+", stripped):
            stripped = "• " + re.sub(r"^[\-\*\u2022\u2022\u2023\u25E6]\s+", "", stripped)
        out.append(stripped)
    return "\n".join(out)


def split_message_safe(html: str, max_len: int = 4000) -> list[str]:
    """Split HTML message at paragraph boundaries so we don't break tags."""
    if not html.strip():
        return []
    if len(html) <= max_len:
        return [html]
    parts = []
    current = []
    current_len = 0
    paragraphs = html.split("\n\n")
    for p in paragraphs:
        p_stripped = p.strip()
        if not p_stripped:
            if current:
                block = "\n\n".join(current)
                if current_len + 2 > max_len and block:
                    parts.append(block)
                    current = []
                    current_len = 0
            continue
        if current_len + len(p) + 2 > max_len and current:
            parts.append("\n\n".join(current))
            current = []
            current_len = 0
        current.append(p)
        current_len += len(p) + 2
    if current:
        parts.append("\n\n".join(current))
    return parts
