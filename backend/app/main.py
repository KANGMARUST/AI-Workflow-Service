import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import StaleDataError

from .config import Settings, settings
from .chat import ChatService
from .chat_routes import router as chat_router
from .database import Database
from .routes import router
from .service import Service

bearer = HTTPBearer(auto_error=False)


def authorize(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    token = request.app.state.config.api_token.get_secret_value()
    if token and (not credentials or not secrets.compare_digest(credentials.credentials.encode(), token.encode())):
        raise HTTPException(401, "인증 토큰이 필요합니다.", headers={"WWW-Authenticate": "Bearer"})


def create_app(config: Settings | None = None):
    config = config or settings
    if config.app_env == "production" and not config.api_token.get_secret_value():
        raise ValueError("production에서는 API_TOKEN을 설정해야 합니다.")

    @asynccontextmanager
    async def lifespan(app):
        db = Database(config)
        db.initialize()
        app.state.db, app.state.service = db, Service(config, db)
        app.state.chat = ChatService(config, db)
        try:
            yield
        finally:
            db.engine.dispose()

    app = FastAPI(title="QuoteFlow API", description="견적서 등록·추출·검토·검색·비교·출력", version="1.0.0", lifespan=lifespan)
    app.state.config = config
    app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in config.cors_origins.split(",") if x.strip()], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    app.include_router(router, prefix=config.api_prefix, dependencies=[Depends(authorize)])
    app.include_router(chat_router, prefix=config.api_prefix, dependencies=[Depends(authorize)])

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse(status_code=422, content={"detail": [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]})

    @app.exception_handler(StaleDataError)
    async def conflict(request, exc):
        return JSONResponse(status_code=409, content={"detail": "동시에 수정된 견적서입니다. 최신 버전을 다시 조회하세요."})

    @app.exception_handler(ValidationError)
    async def result_validation_error(request, exc):
        return JSONResponse(status_code=422, content={"detail": "값의 형식 또는 계산 결과의 정밀도가 허용 범위를 벗어났습니다."})

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        return JSONResponse(status_code=503, content={"detail": "저장소에 접근하지 못했습니다. 데이터베이스 설정을 확인하세요."})

    @app.get("/health", tags=["health"])
    async def health(request: Request):
        with request.app.state.db.sessions() as session:
            session.execute(text("SELECT 1"))
        return {"status": "ok", "environment": config.app_env}

    return app


app = create_app()
