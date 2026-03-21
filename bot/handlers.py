"""Telegram message handlers: detect Reel URL and run pipeline; send recipe only."""
import asyncio
import re

from telegram import Update
from telegram.ext import ContextTypes

import config
from bot.commands import USER_LAST_RECIPE, USER_LAST_SCALE_FACTOR, USER_LAST_TARGET_SERVINGS
from bot.formatting import format_recipe_for_telegram, format_structured_recipe, split_message_safe
from pipeline.download import is_reel_url
from pipeline.recipe_ai import RecipeExtractionError
from pipeline.run import is_recipe_insufficient, run_pipeline

REEL_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?instagram\.com/reel/[\w\-]+",
    re.IGNORECASE,
)


def extract_reel_url(text: str) -> str | None:
    """Return first Instagram Reel URL in text, or None."""
    if not text or not is_reel_url(text):
        return None
    m = REEL_URL_PATTERN.search(text)
    return m.group(0) if m else None


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming message: if it contains a Reel URL, run pipeline and reply with recipe."""
    if not update.message or not update.message.text:
        return
    url = extract_reel_url(update.message.text.strip())
    if not url:
        return
    if not config.TELEGRAM_BOT_TOKEN:
        await update.message.reply_text("Bot is not configured (missing TELEGRAM_BOT_TOKEN).")
        return
    await update.message.reply_text("Processing your reel…")
    try:
        recipe, used_caption_only = await asyncio.to_thread(run_pipeline, url)
    except RecipeExtractionError as e:
        await update.message.reply_text(e.user_message)
        return
    except Exception as e:
        await update.message.reply_text(
            f"Something went wrong: {e!s}\n\n"
            "Common causes: reel could not be downloaded (try again or check the link), "
            "or the video has no detectable recipe content."
        )
        return

    if is_recipe_insufficient(recipe):
        await update.message.reply_text(
            "Could not extract a complete recipe from this reel. Try another video or a longer caption."
        )
        return

    ud = context.user_data
    baseline = recipe.baseline_servings()
    ud[USER_LAST_RECIPE] = recipe.model_dump()
    ud[USER_LAST_SCALE_FACTOR] = 1.0
    ud[USER_LAST_TARGET_SERVINGS] = baseline

    if used_caption_only:
        await update.message.reply_text(
            "Video download skipped; recipe extracted from caption."
        )
    else:
        await update.message.reply_text(
            "Video was downloaded for processing and then deleted."
        )

    markdown = format_structured_recipe(recipe, scale_factor=1.0)
    formatted = format_recipe_for_telegram(markdown)
    parts = split_message_safe(formatted, max_len=4000)
    if not parts:
        await update.message.reply_text("No recipe generated.")
    else:
        for part in parts:
            if part.strip():
                await update.message.reply_text(part, parse_mode="HTML")
