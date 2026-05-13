# ============================================================
# QuantSandbox Makefile
# 标准入口：.venv 为唯一测试/运行环境
# ============================================================

.PHONY: help test test-backend smoke build clean alpha-test alpha-smoke alpha-report alpha-topn

help:
	@echo "QuantSandbox 标准命令"
	@echo ""
	@echo "  make smoke        — 编译 + 构建 + 回归测试（D-9 验收套件）"
	@echo "  make test         — 运行全部非 e2e 测试"
	@echo "  make test-backend — 仅运行后端测试（unit + integration）"
	@echo "  make build        — 前端 npm run build"
	@echo "  make clean        — 清理缓存"
	@echo "  make alpha-test   — Alpha Research 单测 + 集成测试"
	@echo "  make alpha-smoke  — 运行 Alpha Research CLI smoke 脚本"
	@echo "  make alpha-report FACTOR=momentum_60d HORIZON=20 — 输出研究报告"
	@echo "  make alpha-topn FACTOR=momentum_60d TOP_N=10 — 输出 TopN 回测结果"

# ============================================================
# 编译 + 构建 + 回归
# ============================================================
smoke:
	@echo "=== compile ==="
	.venv/bin/python -m compileall -q backend
	@echo "=== frontend build ==="
	cd frontend && npm run build
	@echo "=== contract & strategy tests ==="
	.venv/bin/python -m pytest -q 		tests/unit/test_strategy_contract.py 		tests/unit/test_multi_factor_strategy.py 		tests/unit/test_engine_contract.py
	@echo "=== regression tests ==="
	.venv/bin/python -m pytest -q 		tests/integration/test_strategy_backtest_registry_api.py 		tests/integration/test_portfolio_backtest.py 		tests/integration/test_backtest_summary_diagnostics.py 		tests/integration/test_config_api.py 		tests/integration/test_research_api.py
	@echo ""
	@echo "✅ smoke passed"

# ============================================================
# 完整测试（排除 e2e 和 data_fetch）
# ============================================================
test:
	.venv/bin/python -m pytest tests/ -v --ignore=tests/e2e -k 'not data_fetch'

test-backend:
	.venv/bin/python -m pytest tests/unit tests/integration -v --ignore=tests/e2e -k 'not data_fetch'

# ============================================================
# 前端构建
# ============================================================
build:
	cd frontend && npm run build

# ============================================================
# 缓存清理
# ============================================================
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name node_modules -prune -o -name '*.pyc' -delete 2>/dev/null || true
	@echo "✅ cache cleaned"

alpha-test:
	.venv/bin/python -m pytest tests/unit/test_alpha_dataset_builder.py 		tests/unit/test_factor_library.py 		tests/unit/test_factor_analysis.py 		tests/unit/test_group_backtest.py 		tests/unit/test_topn_backtest.py 		tests/integration/test_research_api.py -q

alpha-smoke:
	.venv/bin/python scripts/run_alpha_smoke.py

alpha-report:
	@test -n "$(FACTOR)" || (echo "FACTOR is required, e.g. make alpha-report FACTOR=momentum_60d HORIZON=20" && exit 1)
	@test -n "$(HORIZON)" || (echo "HORIZON is required, e.g. make alpha-report FACTOR=momentum_60d HORIZON=20" && exit 1)
	.venv/bin/python scripts/run_alpha_report.py --factor $(FACTOR) --horizon $(HORIZON)

alpha-topn:
	@test -n "$(FACTOR)" || (echo "FACTOR is required, e.g. make alpha-topn FACTOR=momentum_60d TOP_N=10" && exit 1)
	@test -n "$(TOP_N)" || (echo "TOP_N is required, e.g. make alpha-topn FACTOR=momentum_60d TOP_N=10" && exit 1)
	.venv/bin/python scripts/run_alpha_topn.py --factor $(FACTOR) --top-n $(TOP_N)
