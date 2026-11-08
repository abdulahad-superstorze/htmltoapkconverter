"""User interface: texts, keyboards, banner and message rendering helpers."""
import os
from html import escape

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from telebot import types
from telebot.apihelper import ApiTelegramException

from config import (
    BANNER_PATH,
    BRAND_NAME,
    CHANNEL_URL,
    SUPPORT_URL,
    VERSION,
)
from core import bot, logger

CAPTION_LIMIT = 1024
LINE = "━━━━━━━━━━━━━━━━━━"

# --------------------------------------------------------------------------
# Static texts (all of them must fit a photo caption: <= 1024 characters)
# --------------------------------------------------------------------------
HOME_TEXT = f"<b>📱 {BRAND_NAME}</b>\n{LINE}\nChoose an action below to continue:"

HELP_TEXT = (
    "<b>📘 HOW IT WORKS</b>\n"
    f"{LINE}\n"
    "<b>1️⃣ Create APK</b> — tap the button or send /newapk\n"
    "<b>2️⃣ App name</b> — up to 80 UTF-16 units / 120 UTF-8 bytes\n"
    "<b>3️⃣ Website</b> — <code>.html</code>, <code>.htm</code> or a <code>.zip</code> with "
    "<code>index.html</code> (up to 10 MiB)\n"
    "<b>4️⃣ Icon</b> — non-interlaced PNG/JPEG (up to 6 MiB, 4 MP)\n"
    "<b>5️⃣ Review &amp; build</b> — confirm and wait for your APK\n\n"
    "💡 <b>Tips</b>\n"
    "• Send the icon as a <b>File</b> for the best quality.\n"
    "• Square icons (e.g. 512×512) look best.\n"
    "• Use /cancel at any time.\n\n"
    "⚠️ Test builds only. Each APK uses a new temporary signing key and "
    "cannot update an earlier build."
)

ABOUT_TEXT = (
    f"<b>ℹ️ ABOUT {BRAND_NAME}</b>\n"
    f"{LINE}\n"
    "Convert an <b>HTML website</b> or <b>ZIP project</b> into an installable "
    "<b>Android APK</b> without leaving Telegram.\n\n"
    "<b>📂 Input:</b> HTML, HTM, ZIP\n"
    "<b>🖼 Icon:</b> PNG, JPEG\n"
    "<b>📦 Output:</b> Android 6.0+ test APK\n"
    "<b>🛠 Engine:</b> APK CreatorX build API\n\n"
    "🔒 Your files are used only to create your build and are cleared from "
    "the bot's memory afterwards.\n\n"
    f"<i>Version {VERSION} • Always test the generated APK on a real device.</i>"
)

CANCELLED_TEXT = "✖️ <b>Cancelled</b>\n\nNothing was changed. Choose an action below:"
CANCELLED_BUILD_TEXT = "✖️ <b>Build cancelled</b>\n\nThe result will be discarded."
EXPIRED_TEXT = "⏳ <b>Session expired</b>\n\nThis session was inactive for too long. Start again below:"
BUILD_BUSY_TEXT = (
    "⏳ <b>A build is already in progress.</b>\n\n"
    "Wait for it to finish, or send /cancel to stop it."
)
UNKNOWN_COMMAND_TEXT = "❓ <b>Unknown command</b>\n\nUse the menu below or /help:"
IDLE_HINT_TEXT = "👋 Tap <b>Create APK</b> to start, or use /help to see how it works:"
STALE_BUTTON_TEXT = "This button is no longer active."
SESSION_EXPIRED_ALERT = "Session expired. Start again."
CRASH_TEXT = "⚠️ <b>Something went wrong</b>\n\nPlease try again. Use /start to return to the menu."


def welcome_text(first_name=None):
    greeting = f"Welcome, <b>{escape(first_name)}</b>! 👋\n\n" if first_name else ""
    return (
        f"<b>📱 {BRAND_NAME}</b>\n"
        f"{LINE}\n"
        f"{greeting}"
        "Turn your <b>HTML website</b> or <b>ZIP project</b> into an "
        "<b>Android APK</b> in a few simple steps.\n\n"
        "✨ <b>What you get</b>\n"
        "• 🌐 HTML / HTM / ZIP support\n"
        "• 🎨 Your own app name &amp; icon\n"
        "• 📦 Ready-to-install test APK\n"
        "• 📊 Live build status\n\n"
        "<i>Fast • Simple • Test-build ready</i>"
    )


# --------------------------------------------------------------------------
# Keyboards
# --------------------------------------------------------------------------
def kb_main_menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("🚀 Create APK", callback_data="menu:new"))
    kb.add(
        types.InlineKeyboardButton("📘 How it works", callback_data="menu:help"),
        types.InlineKeyboardButton("ℹ️ About", callback_data="menu:about"),
    )
    links = []
    if SUPPORT_URL:
        links.append(types.InlineKeyboardButton("💬 Support", url=SUPPORT_URL))
    if CHANNEL_URL:
        links.append(types.InlineKeyboardButton("📢 Channel", url=CHANNEL_URL))
    if links:
        kb.add(*links)
    return kb


def kb_cancel():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✖️ Cancel", callback_data="flow:cancel"))
    return kb


def kb_cancel_build():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✖️ Cancel build", callback_data="flow:cancel"))
    return kb


def kb_back():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("⬅️ Back to menu", callback_data="menu:home"))
    return kb


def kb_back_to_review():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("⬅️ Back to review", callback_data="flow:review"))
    return kb


def kb_confirm():
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(types.InlineKeyboardButton("✅ Build APK", callback_data="flow:build"))
    kb.add(
        types.InlineKeyboardButton("✏️ Name", callback_data="flow:rename"),
        types.InlineKeyboardButton("📄 Website", callback_data="flow:website"),
        types.InlineKeyboardButton("🖼 Icon", callback_data="flow:icon"),
    )
    kb.add(types.InlineKeyboardButton("✖️ Cancel", callback_data="flow:cancel"))
    return kb


def kb_failed():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🔁 Try again", callback_data="flow:build"),
        types.InlineKeyboardButton("✏️ Edit details", callback_data="flow:review"),
    )
    kb.add(types.InlineKeyboardButton("🏠 Main menu", callback_data="menu:home"))
    return kb


# --------------------------------------------------------------------------
# Formatting helpers
# --------------------------------------------------------------------------
def short(text, limit=40):
    """Shorten long names for screens that must fit a 1024-character caption."""
    text = text or ""
    return text if len(text) <= limit else text[: limit - 1] + "…"


def human_size(size):
    if size < 1024:
        return f"{size} B"
    if size < 1024 ** 2:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024 ** 2:.2f} MB"


def format_duration(seconds):
    seconds = int(seconds)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def progress(step, label):
    """step is zero-based: 0..4"""
    cells = ["✅" if i < step else ("🔵" if i == step else "⚪") for i in range(5)]
    return f"<b>Step {step + 1}/5 — {label}</b>\n{'  '.join(cells)}\n\n"


def prompt_name(rename=False):
    if rename:
        return progress(0, "New app name") + "📛 <b>Send the new app name</b>\n\nYou can use up to 80 characters."
    return progress(0, "App name") + "📛 <b>What should your app be called?</b>\n\nSend a name from 1–80 characters."


def prompt_website(name=None):
    saved = f"✅ Name saved: <b>{escape(name)}</b>\n\n" if name else ""
    return (
        progress(1, "Website") + saved +
        "📄 <b>Upload your website</b>\n"
        "Send an <code>.html</code>, <code>.htm</code>, or <code>.zip</code> file (max 10 MiB).\n"
        "<i>A ZIP must contain an index.html file.</i>"
    )


def prompt_icon(filename=None):
    received = f"✅ Website received: <code>{escape(filename)}</code>\n\n" if filename else ""
    return (
        progress(2, "Icon") + received +
        "🖼️ <b>Upload your app icon</b>\n"
        "Send a non-interlaced PNG or JPEG (max 6 MiB, 4 megapixels).\n"
        "<i>Tip: send it as a File and use a square image.</i>"
    )


def error_screen(step, title, detail):
    labels = ["App name", "Website", "Icon"]
    return progress(step, labels[step]) + f"⚠️ <b>{escape(title)}</b>\n\n{escape(detail)}"


def review_text(session):
    html_name, html_bytes = session.website
    icon_name, icon_bytes, _ = session.icon
    fmt, width, height = session.icon_info
    kind = "ZIP project" if html_name.lower().endswith(".zip") else "HTML file"
    text = (
        progress(3, "Review") + "<b>📋 Ready to build</b>\n\n"
        f"📛 <b>Name:</b> {escape(session.app_name)}\n"
        f"📄 <b>Website:</b> <code>{escape(html_name)}</code>\n"
        f"      {kind} • {human_size(len(html_bytes))}\n"
        f"🖼️ <b>Icon:</b> <code>{escape(icon_name)}</code>\n"
        f"      {fmt} • {width}×{height} • {human_size(len(icon_bytes))}\n\n"
    )
    if session.website_note:
        text += f"⚠️ <i>{escape(session.website_note)}</i>\n\n"
    text += "Everything looks good. Start the build?"
    return text


# Build status -------------------------------------------------------------
_PHASE_INDEX = {"queued": 1, "building": 2, "downloading": 3, "delivering": 4}
_SPINNER = ["◐", "◓", "◑", "◒"]


def build_status_text(app_name, phase, attempt, total_attempts, elapsed, frame):
    """A truthful status screen: every line reflects a real stage of the process."""
    current = _PHASE_INDEX.get(phase, 2)
    spinner = _SPINNER[frame % len(_SPINNER)]
    steps = [
        "Files validated",
        "Build slot ready",
        "Building APK" + (f" (attempt {attempt}/{total_attempts})" if attempt > 1 else ""),
        "Downloading APK",
        "Sending to Telegram",
    ]
    lines = []
    for index, label in enumerate(steps):
        if index < current:
            mark = "✅"
        elif index == current:
            mark = spinner
        else:
            mark = "⚪"
        lines.append(f"{mark} {label}")
    if phase == "queued":
        lines[1] = f"{spinner} Waiting for a free build slot"
    return (
        f"<b>⚙️ {BRAND_NAME}</b>\n"
        f"{LINE}\n"
        "<b>BUILD IN PROGRESS</b>\n\n"
        f"📛 <b>{escape(short(app_name))}</b>\n\n"
        + "\n".join(lines) +
        f"\n\n⏱ Elapsed: <b>{format_duration(elapsed)}</b>\n"
        "<i>Builds can take up to a couple of minutes. Cancel stops waiting and discards the result.</i>"
    )


def build_complete_text(app_name, apk_name, size, elapsed):
    return (
        "<b>✅ APK BUILD COMPLETE</b>\n"
        f"{LINE}\n"
        f"📛 <b>{escape(short(app_name))}</b>\n"
        f"📦 <code>{escape(short(apk_name, 60))}</code> • {human_size(size)}\n"
        f"⏱ Built in {format_duration(elapsed)}\n\n"
        "Your APK is being sent below ⬇️"
    )


def apk_caption(app_name, apk_name, size, elapsed):
    return (
        "🎉 <b>Build complete!</b>\n\n"
        f"📛 {escape(short(app_name))}\n"
        f"✅ <code>{escape(short(apk_name, 60))}</code> • {human_size(size)} • ⏱ {format_duration(elapsed)}\n\n"
        "⚠️ Test build only — this APK uses a temporary signing key and cannot update an earlier build."
    )


def build_failed_text(title, detail, hint, status=None):
    code = f" ({status})" if status else ""
    return (
        f"❌ <b>{escape(title)}</b>{code}\n"
        f"{LINE}\n"
        f"{escape(detail)}\n\n"
        f"<i>{escape(hint)}</i>\n\n"
        "💾 Your files are still saved — retry, or edit your details."
    )


# --------------------------------------------------------------------------
# Banner (generated once on start-up; the bot works fine without it)
# --------------------------------------------------------------------------
def _load_font(size):
    for candidate in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return None


def ensure_banner():
    """Create the branded banner image if it does not exist. Never raises."""
    try:
        if os.path.exists(BANNER_PATH):
            return True
        w, h = 1200, 675
        # Gradient on a small canvas, then scaled up (fast).
        sw, sh = 120, 68
        small = Image.new("RGB", (sw, sh))
        px = small.load()
        for y in range(sh):
            for x in range(sw):
                t = (x / sw + y / sh) / 2
                px[x, y] = (int(15 + 18 * t), int(22 + 26 * t), int(53 + 55 * t))
        im = small.resize((w, h), Image.BILINEAR)

        glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.ellipse((780, -160, 1340, 400), fill=(101, 88, 255, 95))
        gd.ellipse((-180, 410, 430, 1030), fill=(0, 207, 191, 55))
        glow = glow.filter(ImageFilter.GaussianBlur(70))
        im = Image.alpha_composite(im.convert("RGBA"), glow)
        d = ImageDraw.Draw(im)

        # Phone illustration (right side)
        dx = 350
        d.rounded_rectangle((435 + dx, 85, 765 + dx, 590), radius=42, fill="#202a4b", outline="#6976b6", width=7)
        d.rounded_rectangle((458 + dx, 132, 742 + dx, 535), radius=14, fill="#0c1329")
        d.rounded_rectangle((555 + dx, 101, 645 + dx, 119), radius=9, fill="#6976b6")
        d.ellipse((579 + dx, 551, 621 + dx, 593), fill="#6976b6")
        d.rounded_rectangle((535 + dx, 230, 665 + dx, 390), radius=22, fill="#665cff")
        d.polygon([(600 + dx, 198), (646 + dx, 240), (554 + dx, 240)], fill="#8d86ff")
        d.line((574 + dx, 219, 560 + dx, 200), fill="#8d86ff", width=8)
        d.line((626 + dx, 219, 640 + dx, 200), fill="#8d86ff", width=8)
        d.ellipse((568 + dx, 278, 584 + dx, 294), fill="white")
        d.ellipse((616 + dx, 278, 632 + dx, 294), fill="white")
        d.rounded_rectangle((570 + dx, 330, 630 + dx, 347), radius=8, fill="#b9b5ff")

        # Brand text (left side)
        big = _load_font(80)
        mid = _load_font(46)
        small_font = _load_font(30)
        if big and mid and small_font:
            d.text((70, 200), "HTML TO APK", font=big, fill="#ffffff")
            d.text((70, 295), "CONVERTER", font=big, fill="#8d86ff")
            d.rounded_rectangle((72, 415, 232, 421), radius=3, fill="#00cfbf")
            d.text((70, 445), "Website  →  Android APK", font=small_font, fill="#b9b5ff")
        im.convert("RGB").save(BANNER_PATH, "PNG", optimize=True)
        return True
    except Exception:
        logger.exception("Could not create the banner image; continuing without it")
        return False


# --------------------------------------------------------------------------
# Message rendering helpers
# --------------------------------------------------------------------------
_banner_file_id = None


def send_with_banner(chat_id, text, markup):
    """Send text with the banner on top; falls back to plain text. Returns the message."""
    global _banner_file_id
    if len(text) <= CAPTION_LIMIT:
        if _banner_file_id:
            try:
                return bot.send_photo(chat_id, _banner_file_id, caption=text, reply_markup=markup)
            except Exception:
                _banner_file_id = None
        if os.path.exists(BANNER_PATH):
            try:
                with open(BANNER_PATH, "rb") as photo:
                    message = bot.send_photo(chat_id, photo, caption=text, reply_markup=markup)
                _banner_file_id = message.photo[-1].file_id
                return message
            except Exception:
                logger.exception("Could not send the banner; sending text instead")
    return bot.send_message(chat_id, text, reply_markup=markup)


def _edit(message, text, markup):
    if message.content_type == "photo":
        return bot.edit_message_caption(text, message.chat.id, message.message_id, reply_markup=markup)
    return bot.edit_message_text(text, message.chat.id, message.message_id, reply_markup=markup)


def render(message, text, markup=None):
    """Show `text` in place of `message` (caption or text). Returns the message now on screen.

    Falls back to sending a new message when the old one cannot be edited
    (deleted, too old) or when the text does not fit a photo caption.
    """
    chat_id = message.chat.id
    if message.content_type == "photo" and len(text) > CAPTION_LIMIT:
        try:
            bot.delete_message(chat_id, message.message_id)
        except Exception:
            pass
        return bot.send_message(chat_id, text, reply_markup=markup)
    try:
        result = _edit(message, text, markup)
        return result if isinstance(result, types.Message) else message
    except ApiTelegramException as exc:
        if "message is not modified" in str(exc).lower():
            return message
        logger.warning("Could not edit message (%s); sending a new one", getattr(exc, "error_code", "?"))
    except Exception:
        logger.warning("Could not edit message; sending a new one")
    return bot.send_message(chat_id, text, reply_markup=markup)


def edit_quiet(message, text, markup=None):
    """Edit without any fallback. Returns seconds to back off (0 when fine)."""
    try:
        _edit(message, text, markup)
        return 0
    except ApiTelegramException as exc:
        if getattr(exc, "error_code", None) == 429:
            try:
                return int(exc.result_json.get("parameters", {}).get("retry_after", 5))
            except Exception:
                return 5
        return 0
    except Exception:
        return 0


def strip_markup(message):
    """Remove the inline keyboard from an old screen so stale buttons disappear."""
    try:
        bot.edit_message_reply_markup(message.chat.id, message.message_id, reply_markup=None)
    except Exception:
        pass
