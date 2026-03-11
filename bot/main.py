"""Run the RecipeMart Telegram bot (long-polling)."""
import logging

from telegram.ext import Application, MessageHandler, filters

import config
from bot.handlers import handle_message

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set. Copy .env.example to .env and set the token.")
        return
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot starting (long-polling)...")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
