"""Central configuration for HTML TO APK CONVERTER.

Everything that can be tuned lives here. Secrets (BOT_TOKEN) are read from
environment variables only and are never stored in the source code.
"""
import os

BRAND_NAME = "HTML TO APK CONVERTER"
VERSION = "2.0.0"


def _env_int(name, default, minimum=0, maximum=None):
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _env_url(name):
    value = os.environ.get(name, "").strip()
    return value if value.startswith(("https://", "http://")) else ""


# --------------------------------------------------------------------------
# Secrets / endpoints
# --------------------------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

# The existing build API. Same endpoint and same request format as before.
API_URL = os.environ.get("API_URL", "").strip() or "https://app-creator-x.ueu.workers.dev/api/v1/build"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BANNER_PATH = os.path.join(BASE_DIR, "html_to_apk_banner.png")

# --------------------------------------------------------------------------
# Upload limits (identical to the original bot / build API rules)
# --------------------------------------------------------------------------
MAX_HTML_SIZE = 10 * 1024 * 1024
MAX_ZIP_SIZE = 10 * 1024 * 1024
MAX_ICON_SIZE = 6 * 1024 * 1024
MAX_ICON_PIXELS = 4_000_000
MAX_TOTAL_BODY = 16_842_752
MAX_TOTAL_FILES = MAX_TOTAL_BODY - 64 * 1024
MAX_APP_NAME_UTF16 = 80
MAX_APP_NAME_UTF8 = 120

# Telegram bots can upload documents up to 50 MB.
MAX_APK_SIZE = 50 * 1024 * 1024

# --------------------------------------------------------------------------
# Reliability / resource management (all optional environment overrides)
# --------------------------------------------------------------------------
MAX_CONCURRENT_BUILDS = _env_int("MAX_CONCURRENT_BUILDS", 3, minimum=1, maximum=20)
SESSION_TTL_SECONDS = _env_int("SESSION_TTL_SECONDS", 30 * 60, minimum=60)
BUILD_COOLDOWN_SECONDS = _env_int("BUILD_COOLDOWN_SECONDS", 10, minimum=0, maximum=600)
CONNECT_TIMEOUT = _env_int("CONNECT_TIMEOUT", 15, minimum=3)
BUILD_TIMEOUT = _env_int("BUILD_TIMEOUT", 240, minimum=30)
BUILD_RETRIES = _env_int("BUILD_RETRIES", 2, minimum=0, maximum=5)
STATUS_REFRESH_SECONDS = 3

# --------------------------------------------------------------------------
# Optional branding links (a button is shown only when the variable is set)
# --------------------------------------------------------------------------
SUPPORT_URL = _env_url("SUPPORT_URL")
CHANNEL_URL = _env_url("CHANNEL_URL")
