from __future__ import annotations

from typing import Sequence

from sqlalchemy import select

from backend.models import WatchlistEntry
from backend.repositories.base import BaseRepository


class WatchlistRepository(BaseRepository[WatchlistEntry]):
    def create(self, entry: WatchlistEntry) -> WatchlistEntry:
        self.session.add(entry)
        self.session.flush()
        return entry

    def get(self, entry_id: str) -> WatchlistEntry | None:
        return self.session.get(WatchlistEntry, entry_id)

    def list_all(self, limit: int = 100) -> Sequence[WatchlistEntry]:
        stmt = select(WatchlistEntry).order_by(WatchlistEntry.created_at.desc()).limit(limit)
        return self.session.execute(stmt).scalars().all()

    def list_by_workflow_run(self, workflow_run_id: str) -> Sequence[WatchlistEntry]:
        stmt = (
            select(WatchlistEntry)
            .where(WatchlistEntry.workflow_run_id == workflow_run_id)
            .order_by(WatchlistEntry.created_at.asc())
        )
        return self.session.execute(stmt).scalars().all()

    def update(
        self,
        entry: WatchlistEntry,
        *,
        entry_reason: str | None = None,
        risk_level=None,
        catalyst_factors=None,
        watch_price_zone: str | None = None,
    ) -> WatchlistEntry:
        if entry_reason is not None:
            entry.entry_reason = entry_reason
        if risk_level is not None:
            entry.risk_level = risk_level
        if catalyst_factors is not None:
            entry.catalyst_factors = catalyst_factors
        if watch_price_zone is not None:
            entry.watch_price_zone = watch_price_zone
        self.session.add(entry)
        self.session.flush()
        return entry

    def delete(self, entry: WatchlistEntry) -> None:
        self.session.delete(entry)

    def delete_by_ids(self, entry_ids: list[str]) -> int:
        from sqlalchemy import delete
        stmt = delete(WatchlistEntry).where(WatchlistEntry.id.in_(entry_ids))
        result = self.session.execute(stmt)
        return result.rowcount
