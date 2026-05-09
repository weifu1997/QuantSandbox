# QuantSandbox 开发计划

> 项目地址：`/root/project/QuantSandbox`
> 远程仓库：`git@github.com:weifu1997/QuantSandbox.git`
> 最近更新：2026-05-09

---

## 一、项目当前状态

### 1.1 已完成主线

| 模块 | 状态 | 说明 |
|---|---|---|
| 低估发现流 Runner | ✅ | 已拆分为 orchestration + helper，去除 pass-through 委托方法 |
| MX 适配层 | ✅ | 已抽公共 `MX_APIKEY` / `MX_API_URL` 读取逻辑 |
| 路由结构 | ✅ | `main.py` 已拆分为 workflow / config / mx / backtest 路由模块 |
| 工作流类型系统 | ✅ | `workflow_type` 字段、枚举、创建路径、测试已补齐 |
| 观察池视图 | ✅ | `/api/watchlist` 支持 `view=all/latest`，并保留 `/api/watchlist/latest` |
| 观察池 PATCH | ✅ | 支持人工编辑并触发重算 |
| watchlist 数值列迁移 | ✅ | 新增并行数值列 + SQL 回填 + `metrics` 嵌套输出 |
| CORS 收紧 | ✅ | 默认仅允许本地前端 origin，可用环境变量覆盖 |
| GitHub 提交 | ✅ | Sprint A / B / C 当前主线均已推送 |

### 1.2 当前数据库事实（以当前本地实例为准）

当前关键表已具备：
- `workflow_runs.workflow_type`
- `watchlist_entries.pe_ttm_num`
- `watchlist_entries.pb_num`
- `watchlist_entries.latest_price_num`
- `watchlist_entries.dividend_yield_num`
- `watchlist_entries.month_return_num`

> 说明：数据库记录数是运行态信息，会持续变化，不再在本文中固化静态条数。

---

## 二、阶段收尾判断

### Sprint A
- ✅ 已完成并验证
- 包括：时间修复、Xuangu 列兼容、僵尸运行清理、观察池 latest/all 视图

### Sprint B
- ✅ 已完成并验证
- 包括：MX 公共配置读取、`main.py` 路由拆分、`runner.py` helper 化、相关回归测试

### Sprint C
- ✅ P1-4 watchlist 数值列迁移已完成
- ✅ P1-5 CORS 收紧已完成
- 🟡 P2 测试 / 文档收尾进行中

---

## 三、当前 API / 运行约定

### 3.1 watchlist
- `GET /api/watchlist`：支持 `view=all|latest`
- `GET /api/watchlist/latest`：`latest` 视图别名
- `PATCH /api/watchlist/{entry_id}`：支持人工编辑并自动重算部分派生字段

### 3.2 watchlist 数值字段
观察池保留两层语义：

1. **兼容文本字段**
   - `pe_ttm`
   - `pb`
   - `latest_price`
   - `dividend_yield`
   - `month_return`

2. **结构化数值字段**
   - API 中通过 `metrics` 嵌套对象返回
   - 数据库存储在并行 `*_num` 列中

### 3.3 CORS
默认允许：
- `http://127.0.0.1:5173`
- `http://localhost:5173`

可通过环境变量覆盖：
- `QUANTSANDBOX_CORS_ORIGINS=http://a.com,http://b.com`

---

## 四、仍可继续推进的事项

### P1 / P2 候选
1. **淘汰池前端页面**
   - 新建 `RejectedPool.vue`
   - 展示 rejected / insufficient_data 候选

2. **观察池前端编辑体验增强**
   - 当前已有 PATCH 接口
   - 可继续做 inline edit 或更好的表单交互

3. **工作流实时进度推送**
   - WebSocket 端点
   - 前端订阅步骤状态变化

4. **自动化定时扫描**
   - cron / scheduler 调用 workflow API
   - 将结果接入通知渠道

5. **测试环境补强**
   - 当前仓库已有 pytest 测试文件
   - 但运行环境中 `pytest` 命令缺失，建议后续补齐测试执行环境

---

## 五、开发环境信息

| 项目 | 值 |
|---|---|
| 项目路径 | `/root/project/QuantSandbox` |
| 后端端口 | `127.0.0.1:8000` |
| 前端端口 | `127.0.0.1:5173` |
| 前端构建 | `cd frontend && npm run build` |
| 后端启动 | `python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000` |
| 数据库 | `data/quantsandbox.sqlite3` |
| Python 版本 | 3.12 |
| Node 版本 | 22 |

---

## 六、参考文档

- `docs/phase1-api.md` — 当前 API 参考
- `docs/phase1-workflow.md` — 工作流概述

---

## 七、建议

1. 后续新功能按“代码改动 + 编译验证 + 接口实测 + 独立 commit”推进
2. 运行态文件（如本地 SQLite DB）不要混入功能提交
3. 对计划文档只保留稳定事实，不固化易漂移的运行时统计
