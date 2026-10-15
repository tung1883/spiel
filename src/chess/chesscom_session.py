"""Chess.com session for the browserless client.

Logging in with a password needs Cloudflare Turnstile (bot check), which a script must not defeat. So the
user logs in normally in their own browser once and pastes the long-lived CHESSCOM_REMEMBERME cookie into the
TUI. That one cookie is enough to mint fresh PHPSESSID / ACCESS_TOKEN cookies over plain HTTP, which is also how
an expired session is renewed. No browser is driven. Delete the session file (or let it expire) to log out.
"""
import json
import os
import re
from pathlib import Path

import httpx

SESSION_FILE = Path(os.environ.get("APPDATA") or Path.home() / ".config") / "tui-games" / "chesscom-session.json"
DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
AUTH_COOKIES = ("PHPSESSID", "ACCESS_TOKEN", "CHESSCOM_REMEMBERME")


def load() -> dict | None:
    try:
        s = json.loads(SESSION_FILE.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    return s if s.get("cookies") and s.get("user_id") else None


def save(cookies: dict[str, str], user_agent: str, user_id: str, username: str) -> None:
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps({"cookies": cookies, "user_agent": user_agent, "user_id": user_id,
                                        "username": username}), "utf-8")
    try:
        os.chmod(SESSION_FILE, 0o600)
    except OSError:
        pass


def clear() -> None:
    SESSION_FILE.unlink(missing_ok=True)


def has_auth(cookies: dict[str, str]) -> bool:
    return any(c in cookies for c in AUTH_COOKIES)


class LoginError(Exception):
    pass


def parse_remember(text: str) -> str:
    """Accepts the bare value, 'CHESSCOM_REMEMBERME=value', or a whole Cookie header."""
    text = text.strip().strip('"')
    m = re.search(r"CHESSCOM_REMEMBERME=([^;\s]+)", text)
    return m.group(1) if m else text


async def login_from_remember(remember: str, user_agent: str = DEFAULT_UA) -> dict:
    """Exchange the remember-me cookie for a full session (plain HTTP) and save it."""
    remember = parse_remember(remember)
    if not remember or len(remember) < 20:
        raise LoginError("that does not look like a CHESSCOM_REMEMBERME value")
    async with httpx.AsyncClient(headers={"User-Agent": user_agent}, follow_redirects=True, timeout=20) as c:
        c.cookies.set("CHESSCOM_REMEMBERME", remember, domain=".chess.com")
        try:
            r = await c.get("https://www.chess.com/home")
        except httpx.HTTPError as e:
            raise LoginError(f"network error: {e}")
        uid = re.search(r'"uuid"\s*:\s*"([0-9a-f-]{36})"', r.text)
        name = re.search(r'"username"\s*:\s*"([^"]+)"', r.text)
        cookies = {ck.name: ck.value for ck in c.cookies.jar}
    if not uid or not has_auth(cookies):
        raise LoginError("chess.com did not accept that cookie (expired or wrong value)")
    save(cookies, user_agent, uid.group(1), name.group(1) if name else "")
    return load()


async def refresh() -> dict:
    """Renew the saved session from its remember-me cookie. Clears the session when that no longer works."""
    old = load()
    if not old or "CHESSCOM_REMEMBERME" not in old["cookies"]:
        clear()
        raise LoginError("not logged in")
    try:
        return await login_from_remember(old["cookies"]["CHESSCOM_REMEMBERME"], old["user_agent"])
    except LoginError:
        clear()
        raise
