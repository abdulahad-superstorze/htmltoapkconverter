"""Input validation: app name, website (HTML / ZIP) and icon.

Every function validates the real file content, not only the file extension.
"""
import io
import os
import zipfile
from collections import namedtuple

from PIL import Image

from config import (
    MAX_APP_NAME_UTF8,
    MAX_APP_NAME_UTF16,
    MAX_ICON_PIXELS,
)

IconInfo = namedtuple("IconInfo", "format width height mime extension")

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def file_extension(filename):
    filename = filename or ""
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def validate_app_name(value):
    """Match CreatorX's 1-80 UTF-16 / 120 UTF-8 name rules. Returns an error or None."""
    value = (value or "").strip()
    if not value:
        return "Please send a non-empty app name."
    utf16_units = len(value.encode("utf-16-le")) // 2
    utf8_bytes = len(value.encode("utf-8"))
    if utf16_units > MAX_APP_NAME_UTF16:
        return f"Name is too long ({utf16_units}/80 UTF-16 units)."
    if utf8_bytes > MAX_APP_NAME_UTF8:
        return f"Name is too large ({utf8_bytes}/120 UTF-8 bytes)."
    if any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in value):
        return "The app name cannot contain control characters."
    return None


def validate_website(filename, content):
    """Validate an uploaded .html/.htm/.zip. Returns (error, warning)."""
    if not content:
        return "The file is empty.", None
    ext = file_extension(filename)
    looks_like_zip = content[:4] in (b"PK\x03\x04", b"PK\x05\x06")

    if ext == "zip":
        return _validate_zip(content)

    # .html / .htm
    if looks_like_zip:
        return "This file is a ZIP archive but has an HTML extension. Rename it to .zip and send it again.", None
    head = content[:8192]
    has_utf16_bom = content[:2] in (b"\xff\xfe", b"\xfe\xff")
    if b"\x00" in head and not has_utf16_bom:
        return "This does not look like a text/HTML file.", None
    if b"<" not in content:
        return "No HTML tags were found in this file.", None
    return None, None


def _validate_zip(content):
    try:
        if not zipfile.is_zipfile(io.BytesIO(content)):
            return "That file is not a valid ZIP archive.", None
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            infos = [info for info in archive.infolist() if not info.is_dir()]
    except zipfile.BadZipFile:
        return "That ZIP archive is corrupted.", None
    except Exception:
        return "That file could not be read as a ZIP archive.", None

    if not infos:
        return "The ZIP archive is empty.", None
    if any(info.flag_bits & 0x1 for info in infos):
        return "Password-protected ZIP files are not supported.", None

    names = [info.filename.replace("\\", "/") for info in infos]
    for name in names:
        parts = name.split("/")
        if name.startswith("/") or ".." in parts:
            return "The ZIP contains unsafe file paths. Please re-create the archive.", None

    lowered = [name.lower() for name in names]
    if "index.html" in lowered:
        return None, None
    if any(name.endswith("/index.html") for name in lowered):
        return None, (
            "index.html was found inside a sub-folder. If the build fails, "
            "place index.html at the top level of the ZIP."
        )
    return "The ZIP must contain an index.html file.", None


def _png_is_interlaced(content):
    # IHDR layout: signature(8) + length(4) + "IHDR"(4) + width(4) height(4)
    # bit depth(1) colour type(1) compression(1) filter(1) interlace(1) -> offset 28
    return len(content) > 28 and content[:8] == _PNG_SIGNATURE and content[28] == 1


def validate_icon(content):
    """Validate the actual image, not only its filename extension.

    Returns (IconInfo | None, error | None).
    """
    if not content:
        return None, "The icon file is empty."
    try:
        with Image.open(io.BytesIO(content)) as image:
            fmt = image.format
            if fmt not in ("PNG", "JPEG"):
                return None, "Only PNG and JPEG icons are supported."
            width, height = image.size
            if width * height > MAX_ICON_PIXELS:
                return None, "The icon is too large: maximum is 4 megapixels."
            if fmt == "PNG" and (_png_is_interlaced(content) or image.info.get("interlace")):
                return None, "Interlaced PNG icons are not supported. Please export a regular PNG."
        # Re-open for a full integrity check (verify() invalidates the image object).
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
    except Exception:
        return None, "That file is not a valid PNG or JPEG image."
    if fmt == "PNG":
        return IconInfo("PNG", width, height, "image/png", "png"), None
    return IconInfo("JPEG", width, height, "image/jpeg", "jpg"), None


def icon_filename(original, info):
    """Keep the user's file name but make the extension match the real format."""
    original = os.path.basename(original or "") or "icon"
    stem = original.rsplit(".", 1)[0] if "." in original else original
    return f"{stem or 'icon'}.{info.extension}"
