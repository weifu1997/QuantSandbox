# QuantSandbox 前端质量审查报告

**审查时间**：2026-05-12  
**审查范围**：4 个策略主链路页面 + API 层 + 后端 Schema  
**审查基准**：`DEVELOPMENT_PLAN.md` 业务目标 + `FRONTEND_FIELD_CONTRACT.md` 字段契约 + `backend/api/schemas.py` 模型定义

---

## 一、审查结果总览

| 维度 | 结果 | 风险项 |
|---|---|---|
| 字段完整性（Step 1） | ✅ **通过** | 0 |
| 前后端对齐（Step 2） | 🟡 **3 项偏差** | 见第二节 |
| 收益评估（Step 3） | 🟡 **1 项高价值缺口** | 见第三节 |

---

## 二、前后端字段对齐验证（Step 2）

### 偏差 1：WalkForward 策略下拉描述缺失 [低] — ✅ **已修复**

| 项 | 详情 |
|---|---|
| 位置 | `WalkForward.vue:19` — `<el-option>` |
| 修复 | `s.label` → `s.description` |
| 状态 | **已修复** |

### 偏差 2：DetailResponse Schema 不完整 [中] — ✅ **已修复**

| 项 | 详情 |
|---|---|
| 位置 | `backend/api/schemas.py:197-205` — `DetailResponse` |
| 修复 | 移除不存在的 `strategy_name`/`strategy_meta`，增加 `name`/`display_name` |
| 状态 | **已修复** |

### 偏差 3：Portfolio 优化/回测接口仅 API 层暴露，无 UI 入口 [中] — ✅ **已修复**

| 项 | 详情 |
|---|---|
| 修复 | WalkForward.vue 增加「📊 组合优化」按钮 + 结果展示卡片 + `startPortfolioOptimize()` 方法 |
| 声明 | `runPortfolioOptimize` 已 import；`optRunning`/`optResult` 状态已添加 |
| Schema | `PortfolioOptimizeResponse` 补充缺失字段 `resolved_tickers`/`start_date`/`end_date`，`errors`→`fetch_errors` |
| 状态 | **已修复**

---

## 三、前端字段完整性检查（Step 1）

**结论：全部通过 ✅**

4 个审查页面中，每一个 reactive 变量均有默认值或动态赋值路径：

| 页面 | 变量数 | 有默认值 | 有赋值路径 | 裸变量风险 |
|---|---|---|---|---|
| Detail.vue | 12 | ✅ | ✅ | 0 |
| WalkForward.vue | 6 | ✅ | ✅ | 0 |
| Dashboard.vue | 9 | ✅ | ✅ | 0 |
| ConfigManager.vue | 14 | ✅ | ✅ | 0 |

关键保护模式：
- `?? '--'` fallback（Detail.vue 度量指标）
- `v-if` 条件渲染守卫（WalkForward 结果区）
- `reactive` 全字段默认值（WalkForward 表单、ConfigManager 账户表单）
- 空数组/空字符串初始化（所有列表）

---

## 四、项目收益评估（Step 3）

### 业务目标对齐

项目核心价值是「策略回测 → Walk-Forward 检验 → 组合优化」分析链路。

| 功能模块 | 前端可达 | 后端就绪 | 收益贡献度 |
|---|---|---|---|
| 策略单标的回测（Detail） | ✅ | ✅ | ⭐⭐⭐ 核心体验 |
| Walk-Forward 检验 | ✅ | ✅ | ⭐⭐⭐ 高级功能 |
| 组合级回测 | ❌ 无 UI | ✅ | ⭐⭐ **未释放价值** |
| 组合级参数优化 | ❌ 无 UI | ✅ | ⭐⭐⭐ **最大未释放价值** |
| 配置管理（动态策略/因子） | ✅ | ✅ | ⭐⭐ 基础能力 |
| 仪表盘汇总 | ✅ | ✅ | ⭐⭐ 多标的概览 |

### 问题修复后预期收益

| 问题 | 预期改善 |
|---|---|
| 偏差 2（Schema 不完整） | 消除新开发者 15-30 分钟的误导排查时间 |
| 偏差 3（Portfolio 优化无 UI） | **释放后端已完成的高价值能力** — 用户可直接在 UI 上对多标的做参数网格搜索，对比最优参数组合。这是当前功能矩阵中最大的价值缺口 |

---

## 五、风险分级与优先级修复建议

| 优先级 | 问题 | 风险等级 | 建议 |
|---|---|---|---|
| P0 | Portfolio 优化无 UI 入口 | 中（价值阻塞） | 在 ConfigManager 或 WalkForward 页面增加 `POST /api/portfolio/optimize` 入口，附结果表格展示 per_ticker 最优参数 |
| P1 | DetailResponse Schema 不完整 | 中（文档误导） | `schemas.py` 增加 `name`, `display_name` 字段 |
| P2 | WalkForward 策略描述 `s.label` → `s.description` | 低（UX 微瑕） | 1 行改动 |

---

## 六、附录：逐页面逐接口对照表

### A. Detail.vue ↔ DetailResponse

| 前端读取 | 后端返回 | 对齐 |
|---|---|---|
| `res.data` | ✅ | ✅ |
| `data.display_name` | 实际有 ❓ Schema 无 | 🟡 Schema 缺失 |
| `data.name` | 实际有 ❓ Schema 无 | 🟡 Schema 缺失 |
| `data.metadata` | ✅ | ✅ |
| `data.klines` | ✅ | ✅ |
| `data.logs` | ✅ | ✅ |

### B. WalkForward.vue ↔ Walk-Forward Response

| 前端读取 | 后端返回 | 对齐 |
|---|---|---|
| `result.status` / `strategy_name` / `window_count` | ✅ | ✅ |
| `result.window_summary.window_status_counts` | ✅ | ✅ |
| `window.optimize_result.evaluated_ticker_count` | ✅ | ✅ |
| `window.optimize_result.per_ticker[].best_params` | ✅ | ✅ |
| `s.label` (策略下拉) | ❌ 返回 `description` | 🔴 字段名不匹配 |

### C. Dashboard.vue ↔ SummaryResponse

| 前端读取 | 后端返回 | 对齐 |
|---|---|---|
| `payload.data[].ticker` / `display_name` / `return_rate` / `trade_count` | ✅ | ✅ |
| `payload.data_source` / `fetch_note` | ✅ | ✅ |
| `data.task_id` / `task_status` (异步) | ✅ | ✅ |

### D. ConfigManager.vue ↔ Config / Strategies / Factors

| 前端读取 | 后端返回 | 对齐 |
|---|---|---|
| `res.data.stock_pool` | ✅ | ✅ |
| `res.data.account.{initial_cash, commission_rate, tax_rate}` | ✅ | ✅ |
| `res.data.strategy.{name, parameters}` | ✅ | ✅ |
| `res?.data?.strategies[].{name, description, parameter_schema}` | ✅ | ✅ |
| `res?.data?.factors[].{name, category, description}` | ✅ | ✅ |
