"""Password-authorized Jupyter sessions bound to Cloud Shell's HttpOnly relay cookie."""

from __future__ import annotations

import hashlib
import time
from typing import TYPE_CHECKING

from jupyter_server.auth.identity import PasswordIdentityProvider, User

if TYPE_CHECKING:
    from jupyter_server.base.handlers import JupyterHandler


class CloudShellIdentityProvider(PasswordIdentityProvider):
    """Never trust the relay cookie alone: authorize it only after Jupyter login."""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._relay_sessions: dict[bytes, tuple[User, float]] = {}

    @staticmethod
    def _relay_key(handler: JupyterHandler) -> bytes | None:
        cookie = handler.get_cookie("auth-token")
        if cookie is None or not 32 <= len(cookie) <= 4096:
            return None
        return hashlib.sha256(cookie.encode()).digest()

    async def get_user(self, handler: JupyterHandler) -> User | None:
        key = self._relay_key(handler)
        now = time.monotonic()
        if key is not None:
            session = self._relay_sessions.get(key)
            if session is not None:
                user, expires = session
                if expires > now and handler.get_cookie("_xsrf"):
                    self._relay_sessions[key] = (user, now + 3600)
                    return user
                del self._relay_sessions[key]
        return await super().get_user(handler)

    def set_login_cookie(self, handler: JupyterHandler, user: User) -> None:
        # Jupyter calls this only after password/token verification. The relay
        # drops Set-Cookie, but its own Secure/HttpOnly cookie reaches requests.
        key = self._relay_key(handler)
        if key is None:
            super().set_login_cookie(handler, user)
            return
        now = time.monotonic()
        self._relay_sessions = {
            stored: session for stored, session in self._relay_sessions.items() if session[1] > now
        }
        if len(self._relay_sessions) >= 32 and key not in self._relay_sessions:
            oldest = min(self._relay_sessions, key=lambda stored: self._relay_sessions[stored][1])
            del self._relay_sessions[oldest]
        self._relay_sessions[key] = (user, now + 3600)

    def clear_login_cookie(self, handler: JupyterHandler) -> None:
        key = self._relay_key(handler)
        if key is not None:
            self._relay_sessions.pop(key, None)
        # Do not clear Azure's cookie or sign the user out of other relay apps.
        super().clear_login_cookie(handler)
