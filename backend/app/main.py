from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from sqlalchemy import text

from app.api.documents import router as documents_router
from app.api.search import router as search_router
from app.api.equipment import router as equipment_router
from app.db.init_equipment import initialize_equipment
from app.api.inspection import router as inspection_router
from app.db.init_vision import initialize_vision
from app.db.init_troubleshooting import initialize_troubleshooting
from app.api.troubleshooting import router as troubleshooting_router
from app.api.viewer import router as viewer_router
from app.db.init_db import initialize
from app.db.session import get_engine
from app.demo_safety import configure_safety


@asynccontextmanager
async def lifespan(app):
    initialize()
    initialize_equipment()
    initialize_vision()
    initialize_troubleshooting()
    yield
    get_engine().dispose()


settings = get_settings()
production = settings.app_env == 'production'
app = FastAPI(title="ABB Guardian: Grounded Troubleshooting", version="0.4.0", lifespan=lifespan,
              docs_url=None if production else '/docs', redoc_url=None if production else '/redoc',
              openapi_url=None if production else '/openapi.json')
configure_safety(app, settings)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins,
                   allow_credentials=False, allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
                   allow_headers=['Content-Type', 'Authorization'])
if not production:
    app.include_router(documents_router)
app.include_router(search_router)
app.include_router(equipment_router)
app.include_router(inspection_router)
app.include_router(troubleshooting_router)
app.include_router(viewer_router)


@app.get("/health")
def health():
    with get_engine().connect() as connection:
        version = connection.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
    return {"status": "ok", "pgvector_version": version, "mode": "evidence_only"}
