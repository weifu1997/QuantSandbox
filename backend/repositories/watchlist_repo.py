from __future__ import annotations

from typing import Sequence

from sqlalchemy import select, func, desc

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
        latest_created = (
            select(
                WatchlistEntry.symbol.label("symbol"),
                func.max(WatchlistEntry.created_at).label("max_created_at"),
            )
            .group_by(WatchlistEntry.symbol)
            .subquery()
        )
        stmt = (
            select(WatchlistEntry)
            .join(
                latest_created,
                (WatchlistEntry.symbol == latest_created.c.symbol)
                & (WatchlistEntry.created_at == latest_created.c.max_created_at),
            )
            .order_by(desc(WatchlistEntry.created_at), desc(WatchlistEntry.entry_date), desc(WatchlistEntry.id))
            .limit(limit)
        )
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
        board: str | None = None,
        pe_ttm: str | None = None,
        pb: str | None = None,
        latest_price: str | None = None,
        dividend_yield: str | None = None,
        month_return: str | None = None,
        st_flag: str | None = None,
    ) -> WatchlistEntry:
        if entry_reason is not None:
            entry.entry_reason = entry_reason
        if risk_level is not None:
            entry.risk_level = risk_level
        if catalyst_factors is not None:
            entry.catalyst_factors = catalyst_factors
        if watch_price_zone is not None:
            entry.watch_price_zone = watch_price_zone
        if board is not None:
            entry.board = board
        if pe_ttm is not None:
            entry.pe_ttm = pe_ttm
        if pb is not None:
            entry.pb = pb
        if latest_price is not None:
            entry.latest_price = latest_price
        if dividend_yield is not None:
            entry.dividend_yield = dividend_yield
        if month_return is not None:
            entry.month_return = month_return
        if st_flag is not None:
            entry.st_flag = st_flag
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
