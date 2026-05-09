from datetime import timedelta

from backend.models import WatchlistEntry, WorkflowRun, WorkflowRunStatus
from backend.models.workflow import WorkflowStepStatus
from backend.models.workflow_step import WorkflowStepRun
from backend.repositories.watchlist_repo import WatchlistRepository
from backend.repositories.workflow_run_repo import WorkflowRunRepository
from backend.repositories.workflow_step_repo import WorkflowStepRunRepository
from backend.utils.time import utcnow


def test_watchlist_repository_supports_all_and_latest_views(db_session):
    run1 = WorkflowRun(user_id='u1', workflow_type='low_value_discovery', status=WorkflowRunStatus.COMPLETED)
    run2 = WorkflowRun(user_id='u2', workflow_type='low_value_discovery', status=WorkflowRunStatus.COMPLETED)
    db_session.add_all([run1, run2])
    db_session.flush()

    repo = WatchlistRepository(db_session)
    older = WatchlistEntry(workflow_run_id=run1.id, symbol='603166', name='福达股份', entry_reason='first')
    newer = WatchlistEntry(workflow_run_id=run2.id, symbol='603166', name='福达股份', entry_reason='second')
    other = WatchlistEntry(workflow_run_id=run1.id, symbol='600000', name='浦发银行', entry_reason='other')
    repo.create(older)
    repo.create(newer)
    repo.create(other)

    all_rows = repo.list_all(limit=10)
    latest_rows = repo.list_latest(limit=10)

    assert len([row for row in all_rows if row.symbol == '603166']) == 2
    latest_symbols = [row.symbol for row in latest_rows]
    assert latest_symbols.count('603166') == 1
    selected = next(row for row in latest_rows if row.symbol == '603166')
    assert selected.entry_reason == 'second'


def test_mark_stale_running_low_value_failed_marks_runs_and_steps(db_session):
    old_started = utcnow() - timedelta(hours=2)
    stale_run = WorkflowRun(
        user_id='u1',
        workflow_type='low_value_discovery',
        status=WorkflowRunStatus.RUNNING,
        started_at=old_started,
    )
    healthy_run = WorkflowRun(
        user_id='u2',
        workflow_type='other_workflow',
        status=WorkflowRunStatus.RUNNING,
        started_at=old_started,
    )
    db_session.add_all([stale_run, healthy_run])
    db_session.flush()

    stale_step = WorkflowStepRun(
        workflow_run_id=stale_run.id,
        step_code='xuangu',
        step_name='Step 1',
        status=WorkflowStepStatus.RUNNING,
        started_at=old_started,
    )
    healthy_step = WorkflowStepRun(
        workflow_run_id=healthy_run.id,
        step_code='xuangu',
        step_name='Step 1',
        status=WorkflowStepStatus.RUNNING,
        started_at=old_started,
    )
    db_session.add_all([stale_step, healthy_step])
    db_session.flush()

    run_repo = WorkflowRunRepository(db_session)
    step_repo = WorkflowStepRunRepository(db_session)

    stale_runs = run_repo.mark_stale_running_low_value_failed(stale_after_minutes=60)
    step_repo.mark_running_steps_failed_for_run_ids([run.id for run in stale_runs])
    db_session.flush()

    assert [run.id for run in stale_runs] == [stale_run.id]
    assert stale_run.status == WorkflowRunStatus.FAILED
    assert stale_run.completed_at is not None
    assert stale_step.status == WorkflowStepStatus.FAILED
    assert stale_step.completed_at is not None
    assert healthy_run.status == WorkflowRunStatus.RUNNING
    assert healthy_step.status == WorkflowStepStatus.RUNNING
