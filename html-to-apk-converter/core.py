"""Shared core: logging (with token redaction) and the TeleBot instance."""
import logging
import sys

import telebot
from telebot import apihelper

from config import BOT_TOKEN


class RedactingFormatter(logging.Formatter):
    """Never let the bot token reach the logs (Telegram file URLs contain it)."""

    def format(self, record):
        text = super().format(record)
        if BOT_TOKEN:
            text = text.replace(BOT_TOKEN, "<redacted-token>")
        return text


def _setup_logging():
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(RedactingFormatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
    # telebot installs its own stderr handler; route it through ours instead.
    telebot.logger.handlers[:] = [handler]
    telebot.logger.propagate = False
    telebot.logger.setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


_setup_logging()
logger = logging.getLogger("html_to_apk_bot")

if not BOT_TOKEN or ":" not in BOT_TOKEN:
    raise SystemExit("Set a valid BOT_TOKEN environment variable before running.")

# Uploading a large APK back to Telegram can take longer than the 30 s default.
apihelper.READ_TIMEOUT = 120

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=True, num_threads=8)
