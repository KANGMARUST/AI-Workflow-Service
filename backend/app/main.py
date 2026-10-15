from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .routes import router
app=FastAPI(title="QuoteFlow API",description="견적서 관리 API 골격",version="0.1.0")
app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
app.include_router(router,prefix=settings.api_prefix)
@app.get("/health",tags=["health"])
async def health(): return {"status":"ok","environment":settings.app_env}
