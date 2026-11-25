import os
import re

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(BACKEND_DIR, "db", "blessing_memory.db")

MISSION_ID_RE = re.compile(r"^FLAME-\d{3,}$")
MAX_PROOF_HASH_LEN = 128
MAX_TEXT_LEN = 2000


def db_path() -> str:
    return os.environ.get("FLAME_DB_PATH") or DEFAULT_DB_PATH


def admin_ids() -> frozenset:
    """Telegram user ids allowed to see operator detail.

    FLAME_ADMIN_IDS is a comma separated list. Unset or empty means nobody is
    an admin (secure by default); /status then shows only the public view.
    """
    raw = os.environ.get("FLAME_ADMIN_IDS", "")
    ids = set()
    for part in raw.split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            ids.add(int(part))
    return frozenset(ids)


def is_admin(user_id: int) -> bool:
    return user_id in admin_ids()
