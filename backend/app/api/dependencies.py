from typing import Annotated

from fastapi import Depends, Query, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..db.repositories.sessions import Session, authenticate

bearer = HTTPBearer(auto_error=False)


def api_session(request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer)]):
    return authenticate(request.app.state.database, credentials.credentials if credentials else None)


class Pagination:
    def __init__(self, limit: Annotated[int, Query(ge=1, le=100)] = 20,
                 offset: Annotated[int, Query(ge=0, le=2**63-1)] = 0):
        self.limit = limit
        self.offset = offset


CurrentSession = Annotated[Session, Depends(api_session)]
Page = Annotated[Pagination, Depends()]

