# QuantSandbox 开发计划

> 最近更新：2026-05-12

## 当前主线

QuantSandbox 当前 alpha 主线聚焦于：
- 回测总览 / 个股详情
- 配置管理
- MX 研究工具
- 新策略体系（`multi_factor_target_weight` 为主，`target_weight_demo` 为 smoke only）

## 已完成的策略体系重构

- 旧策略已删除：`dual_ma` / `bollinger_bands` / `rsi_reversal`
- 新策略注册表启用：`multi_factor_target_weight`
- `target_weight_demo` 保留为 smoke test 示例，不作为研究主线
- 后端主线接口：`/api/config`、`/api/meta`、`/api/summary`、`/api/detail/{ticker}`、`/api/strategies/*`、`/api/mx/*`、`/api/factors`

## 说明

此前的 workflow / watchlist / candidate / position management 规划已从当前 alpha 主线移除，不再作为近期开发目标。
