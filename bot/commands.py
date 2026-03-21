"""Telegram command handlers: /help, /scale, /macros."""
from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.formatting import format_recipe_for_telegram, format_structured_recipe, split_message_safe
from pipeline.recipe_ai import RecipeExtractionError, estimate_macros
from pipeline.recipe_schema import Recipe, scaled_ingredients
from pipeline.run import is_recipe_insufficient

logger = logging.getLogger(__name__)

USER_LAST_RECIPE = "last_recipe"
USER_LAST_SCALE_FACTOR = "last_scale_factor"
USER_LAST_TARGET_SERVINGS = "last_target_servings"

MACRO_DISCLAIMER = (
    "<b>Nutrition estimate</b>: These values are approximate (AI-estimated from ingredients), "
    "not lab-tested. Not medical or dietary advice.\n\n"
)


def _recipe_from_user_data(ud: dict) -> Recipe | None:
    raw = ud.get(USER_LAST_RECIPE)
    if not raw:
        return None
    try:
        return Recipe.model_validate(raw)
    except Exception:
        logger.exception("Invalid last_recipe in user_data")
        return None


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    text = (
        "<b>RecipeMart</b>\n\n"
        "Send a message containing an Instagram <b>Reel URL</b> to extract a recipe.\n\n"
        "<b>Commands</b>\n"
        "• /scale &lt;n&gt; — Scale ingredient amounts for <i>n</i> servings (people). "
        "Uses the recipe’s serving count when present; otherwise baseline <b>4</b> servings.\n"
        "• /macros — Estimate calories and macros (protein, carbs, fat) for the "
        "<i>current</i> scaled batch and per serving.\n\n"
        "<i>Last recipe is kept in memory until the bot restarts or you send another Reel.</i>"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_scale(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    ud = context.user_data
    recipe = _recipe_from_user_data(ud)
    if not recipe or is_recipe_insufficient(recipe):
        await update.message.reply_text(
            "No recipe loaded. Send an Instagram Reel URL first, then use /scale."
        )
        return
    args = context.args or []
    if len(args) != 1:
        await update.message.reply_text("Usage: /scale <number of servings>\nExample: /scale 6")
        return
    try:
        n = float(args[0].replace(",", "."))
    except ValueError:
        await update.message.reply_text("Please send a number, e.g. /scale 6")
        return
    if n <= 0 or n > 1e6:
        await update.message.reply_text("Servings must be a positive number (reasonable size).")
        return

    baseline = recipe.baseline_servings()
    scale_factor = n / baseline
    ud[USER_LAST_SCALE_FACTOR] = scale_factor
    ud[USER_LAST_TARGET_SERVINGS] = n

    preamble = (
        f"**Scaled for {n:g} servings** "
        f"(baseline recipe: {baseline:g} serving{'s' if baseline != 1 else ''})."
    )
    markdown = format_structured_recipe(
        recipe,
        scale_factor=scale_factor,
        preamble=preamble,
    )
    formatted = format_recipe_for_telegram(markdown)
    parts = split_message_safe(formatted, max_len=4000)
    for part in parts:
        if part.strip():
            await update.message.reply_text(part, parse_mode="HTML")


def _fmt_macro_line(label: str, t) -> str:
    return (
        f"{label}: {t.calories:.0f} kcal | "
        f"P {t.protein_g:.1f}g | C {t.carbs_g:.1f}g | F {t.fat_g:.1f}g"
    )


async def cmd_macros(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    ud = context.user_data
    recipe = _recipe_from_user_data(ud)
    if not recipe or is_recipe_insufficient(recipe):
        await update.message.reply_text(
            "No recipe loaded. Send an Instagram Reel URL first, then use /macros."
        )
        return

    scale_factor = float(ud.get(USER_LAST_SCALE_FACTOR, 1.0))
    target_servings = float(ud.get(USER_LAST_TARGET_SERVINGS, recipe.baseline_servings()))
    if target_servings <= 0:
        target_servings = recipe.baseline_servings()

    ingredients = scaled_ingredients(recipe, scale_factor)
    try:
        est = await asyncio.to_thread(estimate_macros, ingredients, target_servings)
    except RecipeExtractionError as e:
        await update.message.reply_text(e.user_message)
        return

    body = (
        _fmt_macro_line("Total (whole batch)", est.total)
        + "\n"
        + _fmt_macro_line(f"Per serving ({target_servings:g} servings)", est.per_serving)
    )
    await update.message.reply_text(MACRO_DISCLAIMER + body, parse_mode="HTML")
