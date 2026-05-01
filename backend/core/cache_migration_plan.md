# 缓存目录重构实施清单

## 目标
- 统一缓存命名，避免同一股票多份碎片缓存
- 用 SQLite 管理缓存索引和覆盖关系
- 保留 Parquet 作为行情数据本体
- 尽量不破坏现有回测和前端接口

## 一、SQLite 表结构
建议新增 `data/cache/cache_index.sqlite`，核心表 `cache_files`：

```sql
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
  created_at TEXT,
  updated_at TEXT,
  remark TEXT
);

CREATE INDEX IF NOT EXISTS idx_cache_files_symbol ON cache_files(symbol);
CREATE INDEX IF NOT EXISTS idx_cache_files_active ON cache_files(symbol, is_active);
CREATE INDEX IF NOT EXISTS idx_cache_files_range ON cache_files(symbol, start_date, end_date);
```

### 简化版也可先落地
若想先做最小实现，可只保留：
- symbol
- file_path
- file_name
- start_date
- end_date
- data_source
- version
- is_active
- updated_at

---

## 二、DataCenter 需要新增的函数

### 1. `_init_cache_index_db()`
- 初始化 SQLite 文件与表结构
- 启动时调用

### 2. `_get_cache_conn()`
- 打开 SQLite 连接
- 统一设置 `row_factory`

### 3. `_upsert_cache_record(...)`
- 写入或更新缓存索引
- 在缓存文件生成或合并后调用

### 4. `_get_cache_record(symbol)`
- 查询当前可用缓存记录
- 返回最近激活的一条或全部记录

### 5. `_cache_covers_range(symbol, start_date, end_date)`
- 基于索引表判断缓存是否覆盖请求区间
- 代替当前靠 glob + 文件名判断

### 6. `_read_cache_file(file_path)`
- 统一读取 parquet
- 兼容未来的加字段逻辑

### 7. `_merge_and_write_cache(symbol, new_df, source, start_date, end_date)`
- 合并旧缓存与新数据
- 按 date 去重、排序
- 写回单票主缓存文件
- 更新索引表

### 8. `_migrate_legacy_cache_files()`
- 扫描旧的 `symbol_start_end.parquet`
- 迁移到新索引
- 尽量不删除旧文件，只先登记

---

## 三、fetch_stock_data() 新流程图

```text
输入 symbol + start_date + end_date + force_update
        |
        v
1. 查 SQLite 索引
        |
        +--> 若找到覆盖区间的 active 缓存
        |        -> 直接读 parquet
        |        -> 返回 df.attrs['data_source'] = 'cache'
        |
        +--> 若找到部分覆盖缓存
        |        -> 计算缺失区间
        |        -> 远端拉缺失段
        |        -> 合并旧缓存与新数据
        |        -> 写回单票主缓存
        |        -> 更新索引
        |        -> 返回合并后的 df
        |
        +--> 若没有缓存
                 -> Tushare 优先
                 -> 失败再 AKShare
                 -> 写入单票主缓存
                 -> 更新索引
                 -> 返回 df
```

---

## 四、旧缓存迁移脚本
建议新增：

```text
scripts/migrate_cache_index.py
```

功能：
1. 扫描 `data/cache/*.parquet`
2. 解析文件名：
   - 旧格式：`symbol_start_end.parquet`
   - 新格式：`symbol.parquet`
3. 读取 parquet 的 date 最小/最大值
4. 将记录写入 SQLite
5. 对同一 symbol 的多个旧文件：
   - 先全部登记为历史记录
   - 选择覆盖区间最长的作为 `is_active=1`
   - 其他设为 `is_active=0`
6. 迁移完成后输出报告

### 建议迁移策略
- **第一阶段不删除旧文件**
- 只做索引登记和 active 标记
- 等运行稳定后，再做归档/清理

---

## 五、文件命名规则

### 新主缓存
```text
{symbol}.parquet
```

例如：
- `sh601318.parquet`
- `sz000858.parquet`

### 旧文件
继续兼容：
- `sh601318_20230101_20240131.parquet`
- `sz000858_20230101_20240131.parquet`

但后续写入优先使用新主缓存。

---

## 六、迁移节奏建议

### Step 1
新增 SQLite 索引，不改现有读写行为。

### Step 2
让 `fetch_stock_data()` 先查索引，再决定读缓存还是拉远端。

### Step 3
新数据统一写成 `symbol.parquet`。

### Step 4
把旧区间文件逐步归档到 `cache_archive/`。

### Step 5
验证稳定后，清理旧文件的 active 状态。

---

## 七、尽量不破坏现有代码的原则
- 保留现有 `fetch_stock_data(symbol, start_date, end_date, force_update)` 接口
- 保留现有前端 `/api/summary` 和 `/api/detail/{ticker}` 接口
- 先通过 `df.attrs` 传递数据源信息，不改响应结构太多
- 索引层先只做“增强”，不要一开始就要求全系统切换

---

## 八、最终推荐架构
- **SQLite**：缓存目录、覆盖关系、文件元信息
- **Parquet**：K 线行情数据
- **DataCenter**：统一入口，负责判断、拉取、合并、落盘、更新索引

