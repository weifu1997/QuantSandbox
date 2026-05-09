import os
import time
import random
import glob
import json
import sqlite3
import hashlib
import urllib.request
import urllib.error
import urllib.parse
import requests
import pandas as pd
import akshare as ak
import yaml
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class DataCenter:
    """
    量化系统的数据神经中枢
    负责调用 akshare / tushare 代理获取 A 股历史数据，并进行本地高速缓存
    """

    def __init__(self, cache_dir: str = "data/cache"):
        self.base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
        self.cache_dir = os.path.join(self.base_path, cache_dir)
        os.makedirs(self.cache_dir, exist_ok=True)

        self.columns_map = {
            "日期": "date", "开盘": "open", "收盘": "close",
            "最高": "high", "最低": "low", "成交量": "volume",
            "成交额": "amount", "振幅": "amplitude", "涨跌幅": "pct_change",
            "涨跌额": "change_amount", "换手率": "turnover"
        }

        # 数据源配置（通过项目配置文件读取）
        self.tickflow_base_url = ""
        self.tickflow_api_key = ""
        self.tushare_base_url = ""
        self.tushare_token = ""
        self.akshare_enabled = True
        self.cache_enabled = True
        self._load_data_source_config()
        logger.info(
            "🔧 [DataCenter] "
            f"TickFlow enabled={bool(self.tickflow_base_url and self.tickflow_api_key)} base_url={self.tickflow_base_url or 'EMPTY'} | "
            f"Tushare enabled={bool(self.tushare_base_url and self.tushare_token)} base_url={self.tushare_base_url or 'EMPTY'}"
        )
        self._stock_meta_cache = {}
        self._source_fail_state = {
            "tickflow": {"fail_count": 0, "cooldown_until": 0.0, "last_error": "", "last_status": ""},
            "tushare": {"fail_count": 0, "cooldown_until": 0.0, "last_error": "", "last_status": ""},
            "akshare": {"fail_count": 0, "cooldown_until": 0.0, "last_error": "", "last_status": ""},
        }
        self.cache_index_db = os.path.join(self.cache_dir, "cache_index.sqlite")
        self._init_cache_index_db()
        self.migrate_legacy_cache_files()

    def _load_data_source_config(self):
        """从项目根 config.yaml 读取数据源配置"""
        config_path = os.path.abspath(os.path.join(self.base_path, "config.yaml"))
        if not os.path.exists(config_path):
            return
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            ds = config.get("data_source", {}) or {}

            tickflow = ds.get("tickflow", {}) or {}
            self.tickflow_base_url = str(tickflow.get("base_url", "")).strip().rstrip("/") if tickflow.get("enabled", False) else ""
            self.tickflow_api_key = str(tickflow.get("api_key", "")).strip() if tickflow.get("enabled", False) else ""

            tushare = ds.get("tushare", {}) or {}
            self.tushare_base_url = str(tushare.get("base_url", "")).strip().rstrip("/") if tushare.get("enabled", False) else ""
            self.tushare_token = str(tushare.get("token", "")).strip() if tushare.get("enabled", False) else ""

            self.akshare_enabled = bool((ds.get("akshare", {}) or {}).get("enabled", True))
            self.cache_enabled = bool((ds.get("cache", {}) or {}).get("enabled", True))
        except Exception as e:
            logger.warning(f"⚠️ [DataCenter] 读取数据源配置失败: {e}")

    def _clean_symbol(self, symbol: str) -> str:
        if symbol.startswith(("sh", "sz")):
            return symbol[2:]
        return symbol

    def _to_ts_code(self, symbol: str) -> str:
        """把 sh600036 / sz000858 / 裸代码 转成 600036.SH / 000858.SZ 供 Tushare / TickFlow 使用"""
        symbol = str(symbol or "").strip()
        code = self._clean_symbol(symbol)
        if symbol.startswith("sh"):
            return f"{code}.SH"
        if symbol.startswith("sz"):
            return f"{code}.SZ"
        if symbol.endswith('.SH') or symbol.endswith('.SZ'):
            return symbol
        if len(code) == 6:
            if code.startswith(('5', '6', '9')):
                return f"{code}.SH"
            return f"{code}.SZ"
        return symbol

    def _get_cache_conn(self):
        conn = sqlite3.connect(self.cache_index_db)
        conn.row_factory = sqlite3.Row
        return conn

    def _clean_ticker_to_code(self, symbol: str) -> str:
        return self._clean_symbol(symbol)

    def get_stock_name(self, symbol: str) -> str:
        """获取股票名称，优先内存缓存，其次 Tushare 元信息，再走本地兜底表。"""
        symbol = str(symbol or "").strip()
        if not symbol:
            return ""

        ts_code = self._to_ts_code(symbol)
        if ts_code in self._stock_meta_cache:
            name = str(self._stock_meta_cache.get(ts_code, {}).get("name", "") or "").strip()
            if name:
                return name

        if self.tushare_base_url and self.tushare_token:
            try:
                meta = self._fetch_stock_meta_from_tushare_proxy(symbol)
                name = str(meta.get("name", "") or "").strip()
                if name:
                    return name
            except Exception:
                pass

        code = self._clean_ticker_to_code(symbol)
        if code:
            for candidate in (code, code.upper(), code.lower()):
                name = self._get_local_stock_name(candidate)
                if name:
                    return name

        return ""

    def _init_cache_index_db(self):
        """初始化缓存索引数据库"""
        with self._get_cache_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    data_source TEXT,
                    version INTEGER DEFAULT 1,
                    is_active INTEGER DEFAULT 1,
                    is_complete INTEGER DEFAULT 1,
                    file_size INTEGER,
                    file_hash TEXT,
                    source_detail TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    remark TEXT
                )
                """
            )
            # 兼容已有库：补 source_detail 字段
            columns = [row[1] for row in conn.execute("PRAGMA table_info(cache_files)").fetchall()]
            if "source_detail" not in columns:
                conn.execute("ALTER TABLE cache_files ADD COLUMN source_detail TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_files_symbol ON cache_files(symbol)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_files_active ON cache_files(symbol, is_active)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_files_range ON cache_files(symbol, start_date, end_date)")
            conn.commit()

    def _upsert_cache_record(self, symbol: str, file_path: str, start_date: str, end_date: str, data_source: str = "remote", source_detail: str = "", is_complete: int = 1, remark: str = ""):
        """写入或更新缓存索引记录"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else None
        file_hash = None
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                file_hash = hashlib.md5(f.read()).hexdigest()

        with self._get_cache_conn() as conn:
            existing = conn.execute(
                "SELECT id FROM cache_files WHERE symbol = ? AND file_path = ? LIMIT 1",
                (symbol, file_path),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE cache_files
                    SET file_name = ?, start_date = ?, end_date = ?, data_source = ?, source_detail = ?,
                        version = version + 1, is_active = 1, is_complete = ?,
                        file_size = ?, file_hash = ?, updated_at = ?, remark = ?
                    WHERE id = ?
                    """,
                    (file_name, start_date, end_date, data_source, source_detail, is_complete, file_size, file_hash, now, remark, existing[0]),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO cache_files (
                        symbol, file_path, file_name, start_date, end_date,
                        data_source, source_detail, version, is_active, is_complete,
                        file_size, file_hash, created_at, updated_at, remark
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?, ?, ?, ?, ?)
                    """,
                    (symbol, file_path, file_name, start_date, end_date, data_source, source_detail, is_complete, file_size, file_hash, now, now, remark),
                )
            conn.execute("UPDATE cache_files SET is_active = 0 WHERE symbol = ? AND file_path <> ?", (symbol, file_path))
            conn.execute(
                "UPDATE cache_files SET source_detail = ? WHERE symbol = ? AND file_path = ?",
                (source_detail or data_source, symbol, file_path),
            )
            conn.commit()

    def migrate_legacy_cache_files(self):
        """启动时扫描旧缓存文件并登记索引（幂等）"""
        try:
            files = [f for f in os.listdir(self.cache_dir) if f.endswith(".parquet")]
            for filename in files:
                full_path = os.path.join(self.cache_dir, filename)
                if not os.path.exists(full_path):
                    continue

                # 幂等保护：已登记同一路径则跳过
                with self._get_cache_conn() as conn:
                    exists = conn.execute(
                        "SELECT id FROM cache_files WHERE file_path = ? LIMIT 1",
                        (full_path,),
                    ).fetchone()
                if exists:
                    continue

                if filename.endswith(".parquet") and filename.count("_") >= 2:
                    parts = filename.replace(".parquet", "").split("_")
                    symbol = parts[0]
                    start_date = parts[-2]
                    end_date = parts[-1]
                    if len(start_date) == 8 and len(end_date) == 8:
                        self._upsert_cache_record(
                            symbol=symbol,
                            file_path=full_path,
                            start_date=start_date,
                            end_date=end_date,
                            data_source="legacy",
                            is_complete=1,
                            remark="auto_migrated_legacy",
                        )
                elif filename.endswith(".parquet") and "_" not in filename:
                    symbol = filename.replace(".parquet", "")
                    try:
                        df = pd.read_parquet(full_path, columns=["date"])
                        if not df.empty and "date" in df.columns:
                            dates = pd.to_datetime(df["date"], errors="coerce").dropna()
                            if not dates.empty:
                                self._upsert_cache_record(
                                    symbol=symbol,
                                    file_path=full_path,
                                    start_date=dates.min().strftime("%Y%m%d"),
                                    end_date=dates.max().strftime("%Y%m%d"),
                                    data_source="legacy",
                                    source_detail="legacy",
                                    is_complete=1,
                                    remark="auto_migrated_legacy",
                                )
                    except Exception:
                        continue
        except Exception as e:
            logger.warning(f"⚠️ [DataCenter] 迁移旧缓存索引失败: {e}")

    def _get_cache_record(self, symbol: str):
        """获取指定股票当前激活的缓存记录"""
        with self._get_cache_conn() as conn:
            cur = conn.execute(
                """
                SELECT * FROM cache_files
                WHERE symbol = ? AND is_active = 1
                ORDER BY end_date DESC, version DESC, updated_at DESC
                LIMIT 1
                """,
                (symbol,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def _get_cache_records(self, symbol: str):
        """获取指定股票所有激活缓存记录"""
        with self._get_cache_conn() as conn:
            cur = conn.execute(
                """
                SELECT * FROM cache_files
                WHERE symbol = ? AND is_active = 1
                ORDER BY start_date ASC, end_date ASC, version DESC, updated_at DESC
                """,
                (symbol,),
            )
            return [dict(row) for row in cur.fetchall()]

    def _load_cache_df(self, file_path: str) -> pd.DataFrame:
        """统一读取 parquet 缓存"""
        df = pd.read_parquet(file_path)
        if not df.empty and "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.sort_values(by="date", ascending=True).reset_index(drop=True)
        return df

    def _write_main_cache(self, symbol: str, df: pd.DataFrame, start_date: str, end_date: str, data_source: str, remark: str = "") -> str:
        """写入单票主缓存并更新索引"""
        file_path = os.path.join(self.cache_dir, f"{symbol}.parquet")
        df.to_parquet(file_path, index=False)
        self._upsert_cache_record(
            symbol=symbol,
            file_path=file_path,
            start_date=start_date,
            end_date=end_date,
            data_source=data_source,
            source_detail=data_source,
            is_complete=1,
            remark=remark,
        )
        return file_path

    def _merge_cache_frames(self, old_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
        """合并旧缓存和新数据，按 date 去重并升序排列"""
        if old_df is None or old_df.empty:
            merged = new_df.copy()
        elif new_df is None or new_df.empty:
            merged = old_df.copy()
        else:
            merged = pd.concat([old_df, new_df], ignore_index=True, sort=False)

        if "date" in merged.columns:
            merged["date"] = pd.to_datetime(merged["date"], errors="coerce")
            merged = merged.dropna(subset=["date"])
            merged = merged.drop_duplicates(subset=["date"], keep="last")
            merged = merged.sort_values(by="date", ascending=True).reset_index(drop=True)
        return merged

    def _get_local_stock_name(self, code: str) -> str:
        local_name_map = {
            "sz000719": "中原传媒",
            "sh600483": "福能股份",
            "sz000883": "湖北能源",
            "sh601598": "中国外运",
            "sh600098": "广州发展",
            "sh600177": "雅戈尔",
        }
        return local_name_map.get(str(code or "").strip(), "")

    def get_source_status(self) -> dict:
        return {
            "tickflow_enabled": bool(self.tickflow_base_url and self.tickflow_api_key),
            "tushare_enabled": bool(self.tushare_base_url and self.tushare_token),
            "akshare_enabled": bool(self.akshare_enabled),
            "cache_enabled": bool(self.cache_enabled),
            "tickflow_last_error": self._source_fail_state.get("tickflow", {}).get("last_error", ""),
            "tickflow_last_status": self._source_fail_state.get("tickflow", {}).get("last_status", ""),
        }

    def get_source_priority(self) -> list[str]:
        return ["tushare", "tickflow", "akshare", "cache"]

    def _normalize_and_enrich(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """统一清洗、补充字段"""
        if df is None or df.empty:
            return pd.DataFrame()

        if "date" not in df.columns:
            df.rename(columns=self.columns_map, inplace=True)

        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.dropna(subset=["date"]).copy()
            df.sort_values(by="date", ascending=True, inplace=True)
            df.reset_index(drop=True, inplace=True)

        try:
            meta = self._fetch_stock_meta_from_tushare_proxy(symbol) if self.tushare_base_url and self.tushare_token else {}
            if "name" not in df.columns or not str(df.get("name", "").iloc[0] if len(df.index) else "").strip():
                df["name"] = meta.get("name", df.get("name", ""))
            if "list_date" not in df.columns:
                df["list_date"] = meta.get("list_date", "")
            if "delist_date" not in df.columns:
                df["delist_date"] = meta.get("delist_date", "")
        except Exception:
            if "name" not in df.columns:
                df["name"] = ""
            if "list_date" not in df.columns:
                df["list_date"] = ""
            if "delist_date" not in df.columns:
                df["delist_date"] = ""

        for col in ["amplitude", "turnover", "name", "list_date", "delist_date"]:
            if col not in df.columns:
                df[col] = ""
        for col in ["open", "high", "low", "close", "volume", "amount", "pct_change", "change_amount", "pre_close"]:
            if col not in df.columns:
                df[col] = pd.NA

        return df

    def _mark_source_success(self, source: str):
        state = self._source_fail_state.setdefault(source, {"fail_count": 0, "cooldown_until": 0.0, "last_error": "", "last_status": ""})
        state["fail_count"] = 0
        state["cooldown_until"] = 0.0
        state["last_error"] = ""
        state["last_status"] = ""

    def _mark_source_failure(self, source: str, cooldown_seconds: int = 120, reason: str = "", status: str = ""):
        state = self._source_fail_state.setdefault(source, {"fail_count": 0, "cooldown_until": 0.0, "last_error": "", "last_status": ""})
        state["fail_count"] = int(state.get("fail_count", 0)) + 1
        state["last_error"] = str(reason or "")
        state["last_status"] = str(status or "")
        if state["fail_count"] >= 3:
            state["cooldown_until"] = time.time() + cooldown_seconds
            logger.warning(f"⚠️ [DataCenter] {source} 进入冷却期 {cooldown_seconds}s")

    def _source_in_cooldown(self, source: str) -> bool:
        state = self._source_fail_state.setdefault(source, {"fail_count": 0, "cooldown_until": 0.0, "last_error": "", "last_status": ""})
        return time.time() < float(state.get("cooldown_until", 0.0))

    def _fetch_from_tickflow(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        if not self.tickflow_base_url or not self.tickflow_api_key:
            raise RuntimeError("TickFlow 配置未启用")

        ts_code = self._to_ts_code(symbol)
        url = f"{self.tickflow_base_url}/v1/klines?symbol={urllib.parse.quote(ts_code)}&period=1d"
        response = requests.get(url, headers={"x-api-key": self.tickflow_api_key}, timeout=20)
        response.raise_for_status()
        data = response.json()
        payload = data.get("data") or {}
        timestamps = payload.get("timestamp") or []
        if not timestamps:
            return pd.DataFrame()

        df = pd.DataFrame({
            "date": pd.to_datetime(timestamps, unit="ms", errors="coerce"),
            "open": payload.get("open", []),
            "high": payload.get("high", []),
            "low": payload.get("low", []),
            "close": payload.get("close", []),
            "volume": payload.get("volume", []),
            "amount": payload.get("amount", []),
            "pre_close": payload.get("prev_close", [pd.NA] * len(timestamps)),
        })
        if "pre_close" in df.columns:
            try:
                df["change_amount"] = pd.to_numeric(df["close"], errors="coerce") - pd.to_numeric(df["pre_close"], errors="coerce")
            except Exception:
                df["change_amount"] = pd.NA
            try:
                pre = pd.to_numeric(df["pre_close"], errors="coerce")
                close_v = pd.to_numeric(df["close"], errors="coerce")
                df["pct_change"] = ((close_v - pre) / pre * 100).replace([pd.NA, pd.NaT], pd.NA)
            except Exception:
                df["pct_change"] = pd.NA
        df["name"] = self.get_stock_name(symbol)
        df["list_date"] = ""
        df["delist_date"] = ""
        df = self._normalize_and_enrich(df, symbol)
        df.attrs["data_source"] = "tickflow"
        return df

    def _download_range_data(self, symbol: str, start_date: str, end_date: str) -> tuple[pd.DataFrame, str]:
        """拉取指定区间数据，返回 df 和数据来源"""
        if start_date > end_date:
            return pd.DataFrame(), "cache"

        if self.tushare_base_url and self.tushare_token and not self._source_in_cooldown("tushare"):
            try:
                logger.info(f"🌐 [DataCenter] 正在从 Tushare 代理下载数据: {symbol} {start_date}-{end_date}...")
                df = self._fetch_from_tushare_proxy(symbol, start_date=start_date, end_date=end_date)
                if not df.empty:
                    self._mark_source_success("tushare")
                    df.attrs["data_source"] = "tushare"
                    return df, "tushare"
                self._mark_source_failure("tushare")
                logger.warning(f"⚠️ [DataCenter] Tushare 返回空数据，切换到 TickFlow: {symbol}")
            except Exception as e:
                self._mark_source_failure("tushare", reason=repr(e), status="error")
                logger.warning(f"⚠️ [DataCenter] Tushare 获取失败，切换到 TickFlow: {symbol}，原因: {e}")
        elif self.tushare_base_url and self.tushare_token:
            logger.warning(f"⚠️ [DataCenter] Tushare 冷却中，跳过本次请求: {symbol}")

        if self.tickflow_base_url and self.tickflow_api_key and not self._source_in_cooldown("tickflow"):
            try:
                logger.info(f"🌐 [DataCenter] 正在从 TickFlow 下载数据: {symbol} {start_date}-{end_date}...")
                df = self._fetch_from_tickflow(symbol, start_date=start_date, end_date=end_date)
                if not df.empty:
                    self._mark_source_success("tickflow")
                    df.attrs["data_source"] = "tickflow"
                    return df, "tickflow"
                self._mark_source_failure("tickflow", reason="TickFlow 返回空数据", status="empty")
                logger.warning(f"⚠️ [DataCenter] TickFlow 返回空数据，切换到 AKShare: {symbol}")
            except urllib.error.HTTPError as e:
                reason = f"HTTP {getattr(e, 'code', '')} {getattr(e, 'reason', '')}"
                if getattr(e, 'code', None) == 403:
                    reason = "HTTP 403 Forbidden：TickFlow API Key 可能无权限或接口未开通"
                self._mark_source_failure("tickflow", reason=reason, status=str(getattr(e, 'code', '')))
                logger.warning(f"⚠️ [DataCenter] TickFlow 获取失败，切换到 AKShare: {symbol}，原因: {reason}")
            except Exception as e:
                self._mark_source_failure("tickflow", reason=repr(e), status="error")
                logger.warning(f"⚠️ [DataCenter] TickFlow 获取失败，切换到 AKShare: {symbol}，原因: {e}")
        elif self.tickflow_base_url and self.tickflow_api_key:
            logger.warning(f"⚠️ [DataCenter] TickFlow 冷却中，跳过本次请求: {symbol}")

        if not self.akshare_enabled:
            return pd.DataFrame(), "cache"

        clean_code = self._clean_symbol(symbol)
        if self._source_in_cooldown("akshare"):
            logger.warning(f"⚠️ [DataCenter] AKShare 冷却中，跳过本次请求: {symbol}")
            return pd.DataFrame(), "remote"
        logger.info(f"🌐 [DataCenter] 正在从东财下载新数据: {symbol} {start_date}-{end_date}...")

        max_retries = 5
        new_df = pd.DataFrame()
        for attempt in range(max_retries):
            try:
                new_df = ak.stock_zh_a_hist(
                    symbol=clean_code,
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq"
                )
                time.sleep(random.uniform(2.5, 5.0))
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(1.0, 3.0)
                    logger.info(f"⚠️ 触发防爬限制。等待 {wait_time:.2f} 秒后进行第 {attempt + 1} 次重试...")
                    time.sleep(wait_time)
                else:
                    self._mark_source_failure("akshare")
                    raise RuntimeError(f"❌ 下载 {symbol} 失败，已达最大重试次数。错误: {e}")

        if new_df.empty:
            self._mark_source_failure("akshare")
            return pd.DataFrame(), "remote"

        self._mark_source_success("akshare")
        new_df.rename(columns=self.columns_map, inplace=True)
        new_df["date"] = pd.to_datetime(new_df["date"], errors="coerce")
        new_df = new_df.dropna(subset=["date"]).copy()
        new_df.sort_values(by="date", ascending=True, inplace=True)
        new_df.reset_index(drop=True, inplace=True)
        new_df["name"] = self.get_stock_name(symbol)
        new_df.attrs["data_source"] = "remote"
        return new_df, "remote"

    def has_cached_data(self, symbol: str) -> bool:
        """判断本地是否已有该股票的任意缓存文件"""
        if self._get_cache_record(symbol) is not None:
            return True
        search_pattern = os.path.join(self.cache_dir, f"{symbol}_*.parquet")
        return len(glob.glob(search_pattern)) > 0

    def _cache_covers_range(self, cache_file: str, start_date: str, end_date: str) -> bool:
        """判断缓存文件名是否覆盖请求区间"""
        base = os.path.basename(cache_file).replace('.parquet', '')
        parts = base.split('_')
        if len(parts) < 3:
            return False
        cache_start = parts[-2]
        cache_end = parts[-1]
        return cache_start <= start_date and cache_end >= end_date

    def get_latest_trade_date(self) -> str:
        """直接返回今天日期，作为默认回测结束日"""
        latest = datetime.now().strftime("%Y%m%d")
        logger.info(f"🔎 [DataCenter] 最新交易日使用 today_date: {latest}")
        return latest

    def _normalize_tushare_daily(self, df: pd.DataFrame) -> pd.DataFrame:
        """将 Tushare 返回字段统一成本项目使用的字段格式"""
        if df.empty:
            return df

        rename_map = {
            "trade_date": "date",
            "ts_code": "ts_code",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "pre_close": "pre_close",
            "change": "change_amount",
            "pct_chg": "pct_change",
            "vol": "volume",
            "amount": "amount",
        }

        df = df.rename(columns=rename_map)

        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], format="%Y%m%d", errors="coerce")

        # 保证后续回测需要的列都存在
        required_columns = [
            "date", "open", "close", "high", "low", "volume",
            "amount", "amplitude", "pct_change", "change_amount", "turnover"
        ]
        for col in required_columns:
            if col not in df.columns:
                df[col] = pd.NA

        # 排序并清理
        df.sort_values(by="date", ascending=True, inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df

    def _tushare_post(self, api_name: str, params: dict, fields: str | None = None) -> dict:
        """通过 HTTP 代理请求 Tushare 接口"""
        if not self.tushare_base_url or not self.tushare_token:
            raise RuntimeError("Tushare 配置未启用")

        payload = {
            "api_name": api_name,
            "token": self.tushare_token,
            "params": params,
        }
        if fields:
            payload["fields"] = fields

        request = urllib.request.Request(
            self.tushare_base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")

        data = json.loads(raw)
        if data.get("code") not in (0, "0", None):
            raise RuntimeError(f"Tushare 返回错误: {data.get('msg', data.get('code'))}")
        return data

    def _fetch_stock_meta_from_tushare_proxy(self, symbol: str) -> dict:
        """尽量从 Tushare 代理拉取股票元信息，用于名称 / 上市日期 / 退市日期判断"""
        ts_code = self._to_ts_code(symbol)
        if ts_code in self._stock_meta_cache:
            return self._stock_meta_cache[ts_code]

        data = self._tushare_post(
            "stock_basic",
            params={"list_status": "L"},
            fields="ts_code,name,list_date,delist_date",
        )
        table = data.get("data") or {}
        fields = table.get("fields") or []
        items = table.get("items") or []
        if not fields or not items:
            return {}

        df = pd.DataFrame(items, columns=fields)
        if "ts_code" not in df.columns:
            return {}

        for _, row in df.iterrows():
            code = str(row.get("ts_code", ""))
            name = str(row.get("name", "") or "")
            list_date = str(row.get("list_date", "") or "")
            delist_date = row.get("delist_date", "")
            if pd.isna(delist_date):
                delist_date = ""
            self._stock_meta_cache[code] = {
                "name": name,
                "list_date": list_date,
                "delist_date": str(delist_date or ""),
            }

        return self._stock_meta_cache.get(ts_code, {})

    def _fetch_from_tushare_proxy(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """通过 HTTP 代理拉取 Tushare 日线数据"""
        if not self.tushare_base_url or not self.tushare_token:
            raise RuntimeError("Tushare 配置未启用")

        ts_code = self._to_ts_code(symbol)
        data = self._tushare_post(
            "daily",
            params={
                "ts_code": ts_code,
                "start_date": start_date,
                "end_date": end_date,
            },
        )

        table = data.get("data") or {}
        fields = table.get("fields") or []
        items = table.get("items") or []

        if not fields or not items:
            return pd.DataFrame()

        df = pd.DataFrame(items, columns=fields)
        df = self._normalize_tushare_daily(df)

        try:
            meta = self._fetch_stock_meta_from_tushare_proxy(symbol)
            df["name"] = meta.get("name", "")
            df["list_date"] = meta.get("list_date", "")
            df["delist_date"] = meta.get("delist_date", "")
        except Exception:
            df["name"] = ""
            df["list_date"] = ""
            df["delist_date"] = ""

        return df

    def fetch_stock_data(
        self,
        symbol: str,
        start_date: str = "20240101",
        end_date: str = "20260421",
        force_update: bool = False,
    ) -> pd.DataFrame:
        """获取股票数据：索引优先、缺口补齐、主缓存写回"""
        main_cache_record = self._get_cache_record(symbol)
        main_cache_file = os.path.join(self.cache_dir, f"{symbol}.parquet")
        cache_miss_note = ""

        # 1) 如果有主缓存且覆盖请求区间，直接读主缓存
        if not force_update and main_cache_record and os.path.exists(main_cache_record["file_path"]):
            cache_start = main_cache_record.get("start_date", "00000000")
            cache_end = main_cache_record.get("end_date", "00000000")
            if cache_start <= start_date and cache_end >= end_date:
                logger.info(f"📦 [DataCenter] 命中主缓存: {os.path.basename(main_cache_record['file_path'])}")
                df = self._load_cache_df(main_cache_record["file_path"])
                mask = (df['date'] >= pd.to_datetime(start_date)) & (df['date'] <= pd.to_datetime(end_date))
                out = df.loc[mask].copy().reset_index(drop=True)
                out.attrs["data_source"] = "cache"
                return out

        base_df = pd.DataFrame()
        fetch_segments = []
        source_tags = []

        # 2) 若主缓存存在但不完整，只计算缺失区间
        if not force_update and main_cache_record and os.path.exists(main_cache_record["file_path"]):
            logger.info(f"⚠️ [DataCenter] 主缓存未覆盖请求区间，尝试补齐: {symbol}")
            base_df = self._load_cache_df(main_cache_record["file_path"])
            if not base_df.empty and "date" in base_df.columns:
                try:
                    base_min_date = base_df["date"].min()
                    base_max_date = base_df["date"].max()
                    req_start = pd.to_datetime(start_date)
                    req_end = pd.to_datetime(end_date)
                    if pd.notna(base_min_date) and req_start < base_min_date:
                        left_end = (pd.Timestamp(base_min_date) - pd.Timedelta(days=1)).strftime("%Y%m%d")
                        if start_date <= left_end:
                            fetch_segments.append((start_date, left_end))
                    if pd.notna(base_max_date) and req_end > base_max_date:
                        right_start = (pd.Timestamp(base_max_date) + pd.Timedelta(days=1)).strftime("%Y%m%d")
                        if right_start <= end_date:
                            fetch_segments.append((right_start, end_date))
                    if fetch_segments:
                        cache_miss_note = "缓存未覆盖区间，自动拉远端"
                except Exception:
                    fetch_segments = [(start_date, end_date)]
                    cache_miss_note = "缓存未覆盖区间，自动拉远端"
            else:
                fetch_segments = [(start_date, end_date)]
                cache_miss_note = "缓存未覆盖区间，自动拉远端"
        else:
            fetch_segments = [(start_date, end_date)]
            if main_cache_record:
                cache_miss_note = "缓存未覆盖区间，自动拉远端"

        # 3) 拉取缺失区间并拼接
        fetched_frames = []
        fetch_sources = []
        for seg_start, seg_end in fetch_segments:
            if seg_start > seg_end:
                continue
            seg_df, seg_source = self._download_range_data(symbol, seg_start, seg_end)
            if not seg_df.empty:
                fetched_frames.append(seg_df)
                fetch_sources.append(seg_source)
                source_tags.append(seg_source)

        new_df = pd.DataFrame()
        if fetched_frames:
            new_df = pd.concat(fetched_frames, ignore_index=True, sort=False)
            new_df = self._normalize_and_enrich(new_df, symbol)
        else:
            # 完全没有缺口但又需要刷新时，拉整段
            if force_update or main_cache_record is None:
                new_df, seg_source = self._download_range_data(symbol, start_date, end_date)
                if not new_df.empty:
                    new_df = self._normalize_and_enrich(new_df, symbol)
                    fetch_sources.append(seg_source)
                    source_tags.append(seg_source)

        if new_df.empty and base_df.empty:
            raise ValueError(f"⚠️ {symbol} 缓存与远端均未返回有效数据。")

        # 4) 合并旧缓存 + 新数据
        merged_df = self._merge_cache_frames(base_df, new_df)
        merged_df = self._normalize_and_enrich(merged_df, symbol)
        if merged_df.empty:
            raise ValueError(f"⚠️ {symbol} 缓存与远端均未返回有效数据。")

        # 5) 写回单票主缓存
        merged_start = merged_df['date'].min().strftime('%Y%m%d')
        merged_end = merged_df['date'].max().strftime('%Y%m%d')
        final_source = fetch_sources[0] if fetch_sources else (main_cache_record.get("data_source", "cache") if main_cache_record else "cache")
        if base_df is not None and not base_df.empty and fetch_sources:
            final_source = "cache_plus_remote"
        elif final_source in ("tushare", "remote") and base_df is not None and not base_df.empty:
            final_source = f"cache_plus_{final_source}"
        self._write_main_cache(
            symbol=symbol,
            df=merged_df,
            start_date=merged_start,
            end_date=merged_end,
            data_source=final_source,
            remark=cache_miss_note,
        )

        # 6) 返回请求区间切片
        mask = (merged_df['date'] >= pd.to_datetime(start_date)) & (merged_df['date'] <= pd.to_datetime(end_date))
        out = merged_df.loc[mask].copy().reset_index(drop=True)
        out.attrs["data_source"] = final_source
        if cache_miss_note:
            out.attrs["fetch_note"] = cache_miss_note
        return out

