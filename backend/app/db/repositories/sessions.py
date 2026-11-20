from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import re
from secrets import token_urlsafe
from uuid import UUID, uuid4

from ...core.errors import ApiProblem
from ..connection import utc_now

SESSION_TTL = timedelta(hours=24)


@dataclass(frozen=True)
class Session:
    id: UUID
    token_hash: str


def create_session(database):
    token = token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + SESSION_TTL
    stamp = now.isoformat(timespec="microseconds")
    with database.connect(write=True) as conn:
        conn.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, ?)",
                     (str(uuid4()), sha256(token.encode()).hexdigest(), stamp, stamp,
                      expires.isoformat(timespec="microseconds")))
    return {"access_token": token, "expires_at": expires}


def authenticate(database, token):
    failure = ApiProblem(401, "UNAUTHORIZED", "유효한 세션 인증이 필요합니다.")
    if not token or re.fullmatch(r"[A-Za-z0-9_-]{43}", token) is None:
        raise failure
    digest = sha256(token.encode()).hexdigest()
    with database.connect(write=True) as conn:
        now = utc_now()
        row = conn.execute("SELECT id FROM sessions WHERE token_hash = ? AND expires_at > ?",
                           (digest, now)).fetchone()
        if row is None:
            raise failure
        conn.execute("UPDATE sessions SET last_used_at = ? WHERE id = ?", (now, row["id"]))
    return Session(UUID(row["id"]), digest)

