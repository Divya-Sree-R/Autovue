from fastapi import FastAPI
from fastapi.middleware.cors import (
    CORSMiddleware,
)

from app.backend.api.reference import (
    router as reference_router,
)


app = FastAPI(
    title="AutoVue API",
    description=(
        "Backend API for AutoVue: "
        "Deep Learning-Based Indian ANPR "
        "Using Vehicle Tracking, OCR, "
        "and Multi-Frame Video Analysis."
    ),
    version="0.1.0",
)


# React/Vite development origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "service": "AutoVue API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "AutoVue API",
        "version": "0.1.0",
    }


app.include_router(
    reference_router
)
