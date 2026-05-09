import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.backtest_endpoints import router as backtest_router
from backend.api.config_endpoints import router as config_router
from backend.api.mx_endpoints import router as mx_router
from backend.api.workflow_endpoints import router as workflow_router
from backend.db.session import init_db, session_scope
from backend.repositories import WorkflowRunRepository, WorkflowStepRunRepository

app = FastAPI(title="Quant Simulate System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(workflow_router)
app.include_router(config_router)
app.include_router(mx_router)
app.include_router(backtest_router)


@app.on_event("startup")
def startup_housekeeping() -> None:
    init_db()
    with session_scope() as s:
        run_repo = WorkflowRunRepository(s)
        step_repo = WorkflowStepRunRepository(s)
        stale_runs = run_repo.mark_stale_running_low_value_failed(stale_after_minutes=60)
        if stale_runs:
            stale_run_ids = [run.id for run in stale_runs]
            step_repo.mark_running_steps_failed_for_run_ids(stale_run_ids)
