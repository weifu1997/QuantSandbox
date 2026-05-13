import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.backtest_endpoints import router as backtest_router
from backend.api.config_endpoints import router as config_router
from backend.api.factor_endpoints import router as factor_router
from backend.api.mx_endpoints import router as mx_router
from backend.api.research_endpoints import router as research_router
from backend.db.session import init_db

app = FastAPI(title="Quant Simulate System API")


def _cors_origins() -> list[str]:
    raw = os.environ.get("QUANTSANDBOX_CORS_ORIGINS", "").strip()
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

app.include_router(config_router)
app.include_router(mx_router)
app.include_router(factor_router)
app.include_router(research_router)
app.include_router(backtest_router)


@app.on_event("startup")
def startup_housekeeping() -> None:
    init_db()
