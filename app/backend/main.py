from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.backend import config
from app.backend.api.reference import router as reference_router
from app.backend.api.jobs import router as jobs_router
from app.backend.api.job_artifacts import router as job_artifacts_router
from app.backend.security import DemoAuthMiddleware


def _frontend_file(root: Path, requested_path: str) -> Path:
    """Serve assets and client routes without exposing files outside the build."""
    components = requested_path.split("/")
    if any(part in {".", ".."} for part in components) or "\\" in requested_path or "\x00" in requested_path:
        raise HTTPException(status_code=404, detail="Not found.")
    if components[0] in {"api", "health", "docs", "redoc", "openapi.json"}:
        raise HTTPException(status_code=404, detail="Not found.")
    candidate = root.joinpath(*components)
    try:
        within_root = candidate.resolve().is_relative_to(root)
    except (OSError, RuntimeError):
        within_root = False
    if not within_root:
        raise HTTPException(status_code=404, detail="Not found.")
    # Avoid following symlinks even when they currently point into the build.
    if any(part.is_symlink() for part in [candidate, *candidate.parents] if part != root and part.is_relative_to(root)):
        raise HTTPException(status_code=404, detail="Not found.")
    if candidate.is_file():
        return candidate
    if Path(requested_path).suffix:
        raise HTTPException(status_code=404, detail="Not found.")
    return _frontend_file(root, "index.html")


def create_app() -> FastAPI:
    application = FastAPI(
        title="AutoVue API",
        description=(
            "Backend API for AutoVue: Deep Learning-Based Indian ANPR "
            "Using Vehicle Tracking, OCR, and Multi-Frame Video Analysis."
        ),
        version="0.1.0",
    )
    if config.FRONTEND_DIST is not None:
        index = config.FRONTEND_DIST / "index.html"
        if not index.is_file() or index.is_symlink():
            raise RuntimeError("AUTOVUE_FRONTEND_DIST must contain a regular index.html build.")
    # Check before constructing the lazy middleware stack: deployment fails closed.
    if config.REQUIRE_AUTH and not (config.AUTH_USERNAME and config.AUTH_PASSWORD):
        raise RuntimeError("AutoVue authentication is required but its secret is missing.")
    if bool(config.AUTH_USERNAME) != bool(config.AUTH_PASSWORD) or ":" in config.AUTH_USERNAME:
        raise RuntimeError("AutoVue authentication requires a valid username and password.")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(
        DemoAuthMiddleware,
        required=config.REQUIRE_AUTH,
        username=config.AUTH_USERNAME,
        password=config.AUTH_PASSWORD,
        allowed_origins=config.CORS_ORIGINS,
    )

    @application.get("/")
    def root():
        if config.FRONTEND_DIST is not None:
            return FileResponse(_frontend_file(config.FRONTEND_DIST, "index.html"), media_type="text/html")
        return {"service": "AutoVue API", "version": "0.1.0", "docs": "/docs", "health": "/health"}

    @application.get("/health")
    def health():
        return {"status": "ok", "service": "AutoVue API", "version": "0.1.0"}

    application.include_router(reference_router)
    application.include_router(jobs_router)
    application.include_router(job_artifacts_router)

    if config.FRONTEND_DIST is not None:
        @application.get("/{requested_path:path}", include_in_schema=False)
        def frontend(requested_path: str):
            return FileResponse(_frontend_file(config.FRONTEND_DIST, requested_path))

    return application


app = create_app()
