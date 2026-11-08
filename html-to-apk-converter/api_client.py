"""Client for the existing APK CreatorX build API.

Request format is unchanged from the original bot:
    POST API_URL  multipart/form-data
        app_name = <text>
        html     = <.html/.htm/.zip file>
        icon     = <png/jpeg file>
    200 + application/vnd.android.package-archive  ->  the APK
    anything else                                  ->  JSON {"error": "..."}
"""
import json
import os
import re
import time
from urllib.parse import unquote

import requests

from config import (
    API_URL,
    BUILD_RETRIES,
    BUILD_TIMEOUT,
    CONNECT_TIMEOUT,
    MAX_APK_SIZE,
)
from core import logger

APK_MIME = "application/vnd.android.package-archive"
RETRYABLE_STATUS = {502, 503, 504}
MAX_ERROR_BODY = 64 * 1024

STATUS_HELP = {
    400: "Please check the app name and uploaded files.",
    401: "The build service rejected the request.",
    403: "The build service rejected the request.",
    413: "The complete request is too large. Try smaller files.",
    415: "The upload format was rejected. Please try again.",
    429: "The build service is rate-limited. Please wait a minute and retry.",
    500: "The build service failed unexpectedly. Please retry with smaller files.",
    502: "The build service is temporarily unavailable. Please retry shortly.",
    503: "The build service is temporarily unavailable. Please retry shortly.",
    504: "The build service timed out. Please retry shortly.",
}


class BuildError(Exception):
    """A build failure with a message that is safe to show to the user."""

    def __init__(self, detail, hint="Please try again later.", status=None):
        super().__init__(detail)
        self.detail = detail
        self.hint = hint
        self.status = status


class BuildCancelled(Exception):
    """Raised when the user cancelled while the build was running."""


class BuildResult:
    def __init__(self, filename, content):
        self.filename = filename
        self.content = content


def _read_limited(response, limit, cancelled):
    chunks = []
    total = 0
    for chunk in response.iter_content(chunk_size=64 * 1024):
        if cancelled():
            raise BuildCancelled()
        if not chunk:
            continue
        total += len(chunk)
        if total > limit:
            return None  # signals "too large"
        chunks.append(chunk)
    return b"".join(chunks)


def _error_from_response(response):
    status = response.status_code
    body = b""
    try:
        body = _read_limited(response, MAX_ERROR_BODY, lambda: False) or b""
    except Exception:
        body = b""
    text = body.decode("utf-8", "replace").strip()
    detail = ""
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            value = payload.get("error") or payload.get("message") or ""
            detail = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        else:
            detail = text
    except ValueError:
        detail = text
    detail = " ".join(detail.split())[:400] or f"HTTP {status}"
    hint = STATUS_HELP.get(status, "Please try again later.")
    retry_after = response.headers.get("Retry-After", "").strip()
    if status == 429 and retry_after.isdigit():
        hint = f"The build service is rate-limited. Please retry in about {retry_after} seconds."
    return BuildError(detail, hint, status)


def sanitize_filename(name, fallback):
    name = os.path.basename((name or "").replace("\\", "/"))
    name = re.sub(r'[\x00-\x1f\x7f<>:"/\\|?*]', "_", name).strip(" .")
    if not name:
        name = fallback
    if not name.lower().endswith(".apk"):
        name += ".apk"
    stem = name[:-4][:90] or "app"
    return f"{stem}.apk"


def apk_filename(response, app_name):
    """Pick a safe APK file name from Content-Disposition, falling back to the app name."""
    fallback = sanitize_filename(app_name, "app")
    disposition = response.headers.get("Content-Disposition", "")
    if not disposition:
        return fallback
    star = re.search(r"filename\*\s*=\s*[^']*'[^']*'([^;]+)", disposition, re.I)
    if star:
        return sanitize_filename(unquote(star.group(1).strip().strip('"')), fallback)
    plain = re.search(r'filename\s*=\s*(?:"([^"]+)"|([^;]+))', disposition, re.I)
    if plain:
        return sanitize_filename((plain.group(1) or plain.group(2)).strip(), fallback)
    return fallback


def _is_apk_response(response):
    ctype = response.headers.get("Content-Type", "").lower()
    return response.status_code == 200 and APK_MIME in ctype


def _sleep(seconds, cancelled):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if cancelled():
            raise BuildCancelled()
        time.sleep(0.25)


def request_build(app_name, website, icon, on_status, cancelled):
    """Call the build API and return a BuildResult.

    website = (filename, bytes); icon = (filename, bytes, mime)
    on_status(phase, attempt) is called with phase in {"building", "downloading"}.
    Raises BuildError / BuildCancelled.
    """
    html_name, html_bytes = website
    icon_name, icon_bytes, icon_mime = icon
    html_mime = "application/zip" if html_name.lower().endswith(".zip") else "text/html"
    total_attempts = BUILD_RETRIES + 1
    last_error = None

    for attempt in range(1, total_attempts + 1):
        if cancelled():
            raise BuildCancelled()
        on_status("building", attempt)
        files = {
            "html": (html_name, html_bytes, html_mime),
            "icon": (icon_name, icon_bytes, icon_mime),
        }
        try:
            with requests.post(
                API_URL,
                data={"app_name": app_name},
                files=files,
                timeout=(CONNECT_TIMEOUT, BUILD_TIMEOUT),
                stream=True,
            ) as response:
                if _is_apk_response(response):
                    on_status("downloading", attempt)
                    content = _read_limited(response, MAX_APK_SIZE, cancelled)
                    if content is None:
                        raise BuildError(
                            "The generated APK is larger than Telegram's 50 MB upload limit.",
                            "Try a smaller website or fewer assets.",
                            response.status_code,
                        )
                    if len(content) < 4 or content[:2] != b"PK":
                        raise BuildError(
                            "The build service returned an invalid APK file.",
                            "Please retry the build.",
                            response.status_code,
                        )
                    return BuildResult(apk_filename(response, app_name), content)

                if response.status_code == 200:
                    raise BuildError(
                        "The build service returned an unexpected response.",
                        "Please retry the build.",
                        200,
                    )

                error = _error_from_response(response)
                if response.status_code in RETRYABLE_STATUS and attempt < total_attempts:
                    last_error = error
                    logger.warning("Build API returned %s (attempt %s/%s); retrying", response.status_code, attempt, total_attempts)
                    _sleep(min(2 ** attempt, 8), cancelled)
                    continue
                raise error

        except (requests.ConnectionError, requests.ConnectTimeout) as exc:
            logger.warning("Build API connection problem (attempt %s/%s): %s", attempt, total_attempts, type(exc).__name__)
            last_error = BuildError(
                "Could not connect to the build service.",
                "Please try again in a moment.",
            )
            if attempt < total_attempts:
                _sleep(min(2 ** attempt, 8), cancelled)
                continue
            raise last_error
        except requests.ReadTimeout:
            raise BuildError(
                "The build service took too long to respond.",
                "Please retry, or try smaller files.",
            )
        except requests.RequestException as exc:
            logger.warning("Build API request failed: %s", type(exc).__name__)
            raise BuildError("The build request failed.", "Please try again later.")

    raise last_error or BuildError("The build failed.", "Please try again later.")
