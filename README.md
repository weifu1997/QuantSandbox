# QuantSandbox

QuantSandbox 是一个面向 A 股研究、复盘和模拟交易的全栈量化沙盘。

## 当前功能

- 首页大盘总览：按股票池批量回测，展示股票代码、股票名称、策略、期末净值、收益率、交易次数
- 单票详情页：点击行可进入单票回测详情
- 配置管理页：
  - 股票池支持多行批量编辑
  - 支持格式化、导出、粘贴自动整理
  - 策略可在 `dual_ma`、`bollinger_bands`、`rsi_reversal` 间切换
- 妙想工具箱：
  - 资讯搜索
  - 金融数据查询
  - 智能选股
  - 模拟组合查询
- 后端 `/api/summary` 已做缓存优先返回，避免首页长时间阻塞
- 首页日期快捷项支持：
  - 近 1 个月
  - 近 3 个月
  - 近 6 个月
  - 近 1 年
  - 今年以来
- 支持本地缓存与 Tushare HTTP 代理（通过 `config.yaml` 配置）

## 技术栈

- 后端：Python 3、FastAPI、Pandas、AKShare、Uvicorn
- 前端：Vue 3、Vite、Element Plus、Axios、Dayjs
- 数据存储：本地 Parquet 缓存

## 启动方式

### 后端

```bash
./scripts/backend_ctl.sh start
./scripts/backend_ctl.sh status
./scripts/backend_ctl.sh logs
./scripts/backend_ctl.sh stop
```

或者手动启动：

```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

默认访问：`http://127.0.0.1:5173`

## 配置说明

项目根目录的 `config.yaml` 记录了：

- `account`：账户资金、佣金、印花税
- `stock_pool`：股票池
- `strategy`：当前策略名称和参数
- `data_source.tushare`：Tushare HTTP 代理配置

### 示例

```yaml
account:
  initial_cash: 15000.0
  commission_rate: 0.00025
  tax_rate: 0.0005

stock_pool:
  - sh600519
  - sz000858

strategy:
  name: dual_ma
  parameters:
    fast_period: 5
    slow_period: 20

data_source:
  tushare:
    enabled: false
    base_url: https://tushare.data.godscode.com.cn/
    token: YOUR_TUSHARE_TOKEN_HERE
```

## 注意事项

- 不要把真实 token 提交到 GitHub
- 首次使用新股票代码时，可能需要联网抓取数据
- 若数据源请求过慢，首页总览会优先返回缓存结果

## 免责声明

本项目仅用于学习、研究与模拟交易演练，不构成任何投资建议。
