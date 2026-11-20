from contextlib import asynccontextmanager
from functools import partial
import logging
from pathlib import Path
import sqlite3
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from .agents.memory import DEFAULT_CHECKPOINT, open_agent
from .api.v1.routes import router
from .core.errors import ApiProblem
from .db.connection import DEFAULT_DATABASE, Database
from .events.anomaly import assess_run
from .events.logging_agent import LoggingAgent
from .events.publisher import Publisher
from .schemas.api import ApiError, ErrorDetail

log = logging.getLogger(__name__)


def create_app(*, database_path=DEFAULT_DATABASE, checkpoint_path=DEFAULT_CHECKPOINT,
               planner=None, run_tool=None, subscriber_factory=LoggingAgent):
    if Path(database_path).resolve() == Path(checkpoint_path).resolve():
        raise ValueError("Business DB and checkpoint paths must be separate.")
    database = Database(database_path)

    @asynccontextmanager
    async def lifespan(app):
        database.initialize()
        app.state.database = database
        subscribers = []
        if subscriber_factory is not None:
            try:
                subscribers.append(subscriber_factory(database))
            except Exception:
                log.warning("YKP event subscriber could not start")
        app.state.publisher = Publisher(*subscribers)
        with open_agent(checkpoint_path, planner=planner, run_tool=run_tool,
                        assess=partial(assess_run, database)) as agent:
            app.state.agent = agent
            yield

    app = FastAPI(title="Youth Kitty Planner", version="1.0", lifespan=lifespan)

    @app.middleware("http")
    async def api_response(request: Request, call_next):
        request.state.request_id = uuid4()
        try:
            response = await call_next(request)
        except sqlite3.OperationalError:
            log.warning("YKP database operation failed")
            response = _error(request, 503, "SERVICE_UNAVAILABLE", "잠시 후 다시 시도해 주세요.")
        except Exception:
            log.warning("YKP request failed")
            response = _error(request, 500, "UNKNOWN_ERROR", "요청을 처리하지 못했습니다.")
        if request.url.path.startswith("/api/v1/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ApiProblem)
    async def api_error(request: Request, error: ApiProblem):
        headers = {"WWW-Authenticate": "Bearer"} if error.status == 401 else None
        return _error(request, error.status, error.code, error.message, headers, details=error.details)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError):
        return _error(request, 422, "INVALID_ARGUMENT", "요청 값을 확인해 주세요.")

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        code, message = {
            404: ("NOT_FOUND", "요청한 리소스를 찾을 수 없습니다."),
            405: ("METHOD_NOT_ALLOWED", "지원하지 않는 요청 방식입니다."),
        }.get(error.status_code, ("HTTP_ERROR", "요청을 처리하지 못했습니다."))
        return _error(request, error.status_code, code, message, error.headers)

    app.include_router(router)
    return app


def _error(request, status, code, message, headers=None, *, details=None):
    body = ApiError(error=ErrorDetail(code=code, message=message, request_id=request.state.request_id, details=details))
    return JSONResponse(body.model_dump(mode="json", exclude_none=True), status_code=status, headers=headers)


app = create_app()

