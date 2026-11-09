import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError, HTTPException as FastAPIHTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import IntegrityError

from db.database import engine, Base
from db import models  # Ensures all models are registered
from db.schemas.response import (
    ApiResponse,
    error_response,
    success_response,
    parse_integrity_error,
)
from routers import role, user, upload, accessions, agents, observations, tables

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create missing tables in Postgres on app startup if database is available
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as exc:
        logger.warning(
            "Could not auto-create database tables on startup (DB may be offline or in test mode): %s",
            exc,
        )
    yield


app = FastAPI(
    title="Marine Data Management & Bulk Excel Processor API",
    description="FastAPI Backend for Postgres database bulk uploading of Excel sheets for marine surveys, accessions, and agents.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add your Vite frontend URLs here
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Enable CORS for React frontend (Vite default is 5173 / 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# Custom Global Exception Handlers (Standardized JSON Envelope)
# ---------------------------------------------------------

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Format request validation errors (e.g., missing required fields, invalid types)
    into a human-readable list and a standardized response envelope.
    """
    errors = []
    for err in exc.errors():
        loc = [str(x) for x in err.get("loc", []) if x not in ("body", "query", "path")]
        field = ".".join(loc) if loc else "field"
        msg = err.get("msg", "Invalid value")
        errors.append(f"{field}: {msg}")

    summary = (
        f"Validation error: {errors[0]}"
        if len(errors) == 1
        else "Validation failed for one or more fields. Please check your input."
    )
    return error_response(
        message=summary,
        errors=errors,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


@app.exception_handler(FastAPIHTTPException)
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Catch HTTPExceptions and wrap them in the standardized error envelope.
    Supports detail as string, dict, or list.
    """
    detail = exc.detail
    if isinstance(detail, dict):
        message = detail.get("message") or detail.get("detail") or "Request failed."
        errors = detail.get("errors") or []
        data = detail.get("data")
    elif isinstance(detail, list):
        message = "Validation error"
        errors = [str(item) for item in detail]
        data = None
    else:
        message = str(detail) if detail else "Request failed."
        errors = []
        data = None

    headers = getattr(exc, "headers", None)
    return error_response(
        message=message,
        errors=errors,
        status_code=exc.status_code,
        data=data,
        headers=headers,
    )


@app.exception_handler(IntegrityError)
async def integrity_exception_handler(request: Request, exc: IntegrityError):
    """
    Handle database conflicts (e.g. duplicate unique keys, invalid foreign keys)
    that were not caught inside route handlers.
    """
    logger.warning("Database integrity constraint violation: %s", exc)
    message, errors = parse_integrity_error(exc)
    return error_response(
        message=message,
        errors=errors,
        status_code=status.HTTP_409_CONFLICT,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Catch-all for unhandled server exceptions (500 Internal Server Error).
    """
    logger.exception("Unhandled server error: %s", exc)
    return error_response(
        message="An unexpected internal server error occurred. Please try again later.",
        errors=[str(exc)] if app.debug else [],
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


# ---------------------------------------------------------
# Application Routers
# ---------------------------------------------------------

app.include_router(upload.router)
app.include_router(accessions.router)
app.include_router(agents.router)
app.include_router(observations.router)
app.include_router(role.router)
app.include_router(tables.router)

try:
    if hasattr(user, "router"):
        app.include_router(user.router)
except Exception:
    pass


@app.get("/", response_model=ApiResponse[dict])
async def read_root():
    """Root status endpoint returning standardized API envelope."""
    return {
        "success": True,
        "message": "Welcome to the Marine Data Management & Bulk Excel Processor API",
        "data": {
            "status": "online",
            "app": "Marine Data Management & Bulk Excel Processor API",
            "database": "PostgreSQL",
            "docs": "/docs",
        },
        "errors": [],
    }
