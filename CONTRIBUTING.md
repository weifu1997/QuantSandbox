# Contributing Guide

感谢你愿意为 QuantSandbox 贡献代码。

## 适合的贡献内容

- 修复 bug
- 优化页面样式与交互
- 完善 README、文档和示例
- 增加或优化策略
- 改进数据源兼容性与缓存逻辑

## 开发约定

- 保持中文注释与中文交互说明为主
- 涉及策略或数据逻辑时，优先保证可验证、可回滚
- 不要把真实 token、密钥、私密配置提交到仓库
- 前端和后端改动后，尽量保持构建可通过

## 建议流程

1. Fork 或新建分支
2. 修改代码
3. 本地验证：
   - 后端：`python3 -m py_compile backend/main.py`
   - 前端：`cd frontend && npm run build`
4. 提交清晰的 commit message
5. 发起 Pull Request

## 提交建议

- `feat:` 新功能
- `fix:` 修复问题
- `docs:` 文档修改
- `refactor:` 重构
- `chore:` 例行维护

## 额外建议

如果你新增策略，最好同时补：
- 策略说明
- 默认参数
- 配置页入口
- 至少一个回测验证样例
