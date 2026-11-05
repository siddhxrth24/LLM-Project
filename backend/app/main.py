from contextlib import asynccontextmanager
import asyncio
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    courses_router,
    documents_router,
    schedule_router,
    settings_router,
    syllabus_router,
    topics_router,
)
from app.core.config import settings
from app.core.database import init_db
from app.core.logging_config import logger
from app.services.llm_service import get_llm_service


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown events."""
    logger.info(f"Initializing {settings.APP_NAME} v{settings.APP_VERSION}...")

    # 1. Initialize SQLite tables, directories, and FTS5
    try:
        init_db()
    except Exception as exc:
        logger.exception(f"Database initialization error: {exc}")
        raise

    # Load the local model before accepting requests so parsing does not pay the
    # model initialization cost on the first upload.
    llm = get_llm_service()
    try:
        loaded = await asyncio.to_thread(llm.load_model)
        if loaded and llm.is_loaded():
            await asyncio.to_thread(llm.generate, "Reply with OK.", 1, 0.0)
            app.state.llm_ready = True
            logger.info("Local LLM loaded and passed startup inference check.")
        else:
            app.state.llm_ready = False
            logger.error(
                "Local LLM is not ready. Syllabus parsing will be unavailable until the "
                "configured model files are installed and the backend is restarted."
            )
    except Exception as exc:
        app.state.llm_ready = False
        logger.exception(f"Local LLM startup check failed: {exc}")

    logger.info("Application startup complete.")
    yield
    logger.info("Application shutting down.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Offline AI Learning Platform API for syllabus parsing, document RAG, and deterministic scheduling.",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# CORS Configuration
allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception Handlers
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    logger.warning(f"HTTPException [{exc.status_code}] on {request.url.path}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": True, "detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    logger.warning(f"Validation error on {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": True, "detail": exc.errors()},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(f"Unhandled server error on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": True, "detail": "An internal server error occurred."},
    )


# Mount Static Uploads
settings.resolved_upload_dir.mkdir(parents=True, exist_ok=True)
app.mount(
    "/uploads",
    StaticFiles(directory=str(settings.resolved_upload_dir)),
    name="uploads",
)

# Register Routers
app.include_router(courses_router)
app.include_router(documents_router)
app.include_router(syllabus_router)
app.include_router(schedule_router)
app.include_router(topics_router)
app.include_router(settings_router)


@app.get("/", tags=["health"])
async def root() -> dict[str, str]:
    """Root health and discovery endpoint."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "online",
        "docs": "/docs" if settings.DEBUG else "disabled",
    }


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
