from __future__ import annotations

import math

import pandas as pd

from backend.research.factor_library import ResearchFactorLibrary, get_research_factor_library
from backend.research.schemas import FactorICReport, HorizonICStats


def _safe_corr(x: pd.Series, y: pd.Series, method: str = "pearson") -> float | None:
    joined = pd.concat([x, y], axis=1).dropna()
    if len(joined) < 2:
        return None
    a = joined.iloc[:, 0]
    b = joined.iloc[:, 1]
    if method == "spearman":
        a = a.rank(method="average")
        b = b.rank(method="average")
    if a.nunique() <= 1 or b.nunique() <= 1:
        return None
    value = a.corr(b, method="pearson")
    if value is None or pd.isna(value) or math.isinf(float(value)):
        return None
    return float(value)


def _series_std(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    result = pd.Series(values, dtype="float64").std(ddof=1)
    if pd.isna(result):
        return 0.0
    return float(result)



def _monthly_ic_map(ic_by_date: list[tuple[pd.Timestamp, float]]) -> dict[str, float]:
    if not ic_by_date:
        return {}
    df = pd.DataFrame(ic_by_date, columns=["date", "ic"])
    df["month"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m")
    grouped = df.groupby("month", sort=True)["ic"].mean()
    return {str(k): float(v) for k, v in grouped.items() if pd.notna(v)}



def analyze_factor_ic(
    dataset: pd.DataFrame,
    factor_name: str,
    horizons: list[int],
    min_cross_section: int = 10,
    factor_library: ResearchFactorLibrary | None = None,
) -> FactorICReport:
    library = factor_library or get_research_factor_library()
    factor = library.get(factor_name)
    warnings: list[str] = []
    horizons_report: dict[int, HorizonICStats] = {}

    for horizon in horizons:
        future_col = f"future_return_{horizon}d"
        factor_col = f"factor:{factor_name}"
        if factor_col not in dataset.columns:
            raise KeyError(f"missing factor column: {factor_col}")
        if future_col not in dataset.columns:
            raise KeyError(f"missing future return column: {future_col}")

        ic_values: list[float] = []
        rank_ic_values: list[float] = []
        ic_by_date: list[tuple[pd.Timestamp, float]] = []
        total_rows = 0
        usable_rows = 0

        grouped = dataset.groupby("date", sort=True)
        skipped_dates = 0

        for date_value, group in grouped:
            total_rows += len(group)
            valid_group = group.copy()
            if "is_valid_sample" in valid_group.columns:
                valid_group = valid_group.loc[valid_group["is_valid_sample"] == True].copy()

            x_raw = pd.to_numeric(valid_group[factor_col], errors="coerce")
            y_raw = pd.to_numeric(valid_group[future_col], errors="coerce")
            usable = pd.concat([x_raw, y_raw], axis=1).dropna()
            usable_rows += len(usable)

            if len(usable) < min_cross_section:
                skipped_dates += 1
                continue

            x = usable.iloc[:, 0]
            y = usable.iloc[:, 1]
            if factor.higher_is_better is False:
                x = -x

            ic = _safe_corr(x, y, method="pearson")
            rank_ic = _safe_corr(x, y, method="spearman")

            if ic is not None:
                ic_values.append(ic)
                ic_by_date.append((pd.Timestamp(date_value), ic))
            if rank_ic is not None:
                rank_ic_values.append(rank_ic)

        if skipped_dates:
            warnings.append(
                f"factor={factor_name} horizon={horizon}: {skipped_dates} dates skipped by min_cross_section={min_cross_section}"
            )

        ic_mean = float(pd.Series(ic_values, dtype="float64").mean()) if ic_values else 0.0
        rank_ic_mean = float(pd.Series(rank_ic_values, dtype="float64").mean()) if rank_ic_values else 0.0
        ic_std = _series_std(ic_values)
        rank_ic_std = _series_std(rank_ic_values)
        ic_ir = ic_mean / ic_std if ic_std > 0 else 0.0
        rank_ic_ir = rank_ic_mean / rank_ic_std if rank_ic_std > 0 else 0.0
        positive_ic_ratio = (
            sum(1 for value in ic_values if value > 0) / len(ic_values)
            if ic_values
            else 0.0
        )
        missing_ratio = 1.0 - (usable_rows / total_rows) if total_rows > 0 else 1.0
        missing_ratio = max(0.0, min(1.0, float(missing_ratio)))

        horizons_report[horizon] = HorizonICStats(
            horizon=horizon,
            ic_mean=ic_mean,
            ic_std=ic_std,
            ic_ir=ic_ir,
            rank_ic_mean=rank_ic_mean,
            rank_ic_std=rank_ic_std,
            rank_ic_ir=rank_ic_ir,
            positive_ic_ratio=float(positive_ic_ratio),
            sample_count=len(ic_values),
            missing_ratio=missing_ratio,
            monthly_ic_series=_monthly_ic_map(ic_by_date),
        )

    return FactorICReport(
        factor_name=factor_name,
        horizons=horizons_report,
        warnings=warnings,
    )
