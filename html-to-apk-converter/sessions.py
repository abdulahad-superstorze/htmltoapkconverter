"""In-memory session store (one session per chat) with expiry and cooldowns."""
import threading
import time


class Session:
    """State of one user's APK creation flow.

    step is one of: name, website, icon, review, building
    """

    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.step = "name"
        self.app_name = None
        self.website = None        # (filename, bytes)
        self.website_note = None   # optional warning shown on the review screen
        self.icon = None           # (filename, bytes, mime)
        self.icon_info = None      # (format, width, height)
        self.ui_message = None     # the bot message currently acting as the "screen"
        self.editing = False       # True while changing one item from the review screen
        self.building = False
        self.cancelled = False
        self.lock = threading.RLock()     # guards step transitions
        self.ui_lock = threading.Lock()   # serialises edits of ui_message
        self.updated_at = time.monotonic()

    def touch(self):
        self.updated_at = time.monotonic()

    def release_files(self):
        self.website = None
        self.icon = None


class SessionStore:
    def __init__(self):
        self._sessions = {}
        self._cooldowns = {}
        self._lock = threading.Lock()

    def get(self, chat_id):
        with self._lock:
            return self._sessions.get(chat_id)

    def create(self, chat_id):
        session = Session(chat_id)
        with self._lock:
            old = self._sessions.get(chat_id)
            self._sessions[chat_id] = session
        if old is not None:
            old.cancelled = True
            old.release_files()
        return session

    def discard(self, chat_id):
        """Remove the session, mark it cancelled and return it (or None)."""
        with self._lock:
            session = self._sessions.pop(chat_id, None)
        if session is not None:
            session.cancelled = True
            session.release_files()
        return session

    def discard_if(self, session):
        """Remove the session only if it is still the active one."""
        with self._lock:
            if self._sessions.get(session.chat_id) is session:
                del self._sessions[session.chat_id]
        session.release_files()

    def pop_expired(self, ttl):
        now = time.monotonic()
        expired = []
        with self._lock:
            for chat_id, session in list(self._sessions.items()):
                if not session.building and now - session.updated_at > ttl:
                    expired.append(self._sessions.pop(chat_id))
        for session in expired:
            session.cancelled = True
            session.release_files()
        return expired

    def cooldown_remaining(self, chat_id, cooldown):
        if cooldown <= 0:
            return 0
        with self._lock:
            last = self._cooldowns.get(chat_id)
        if last is None:
            return 0
        return max(0, int(cooldown - (time.monotonic() - last) + 0.999))

    def mark_build(self, chat_id):
        with self._lock:
            self._cooldowns[chat_id] = time.monotonic()

    def prune_cooldowns(self, max_age=3600):
        now = time.monotonic()
        with self._lock:
            for chat_id, stamp in list(self._cooldowns.items()):
                if now - stamp > max_age:
                    del self._cooldowns[chat_id]
