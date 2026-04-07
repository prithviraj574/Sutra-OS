import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.runtime.router import router as runtime_router

app = FastAPI(title="Sutra OS API")

frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/message")
def message() -> dict[str, str]:
    return {"message": "Hello from FastAPI"}


app.include_router(runtime_router)
