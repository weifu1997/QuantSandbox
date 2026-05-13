# QuantSandbox

> 一个面向 A 股研究、复盘与模拟交易的全栈量化沙盘。

QuantSandbox 提供从**股票池配置**、**策略切换**、**大盘总览回测**到**单票详情下钻**的一体化研究流程，并集成了妙想工具箱，方便做资讯检索、数据查询与选股探索。

## 截图

### 首页总览

![首页总览](image_3.png)

### 单票详情

![单票详情](image_4.png)

![单票详情-日志](image_5.png)

### 配置管理

![配置管理](image_1.png)

### 妙想工具箱

![妙想工具箱](image_2.png)

## 主要功能

- **首页大盘总览**
  - 按股票池批量回测
  - 展示股票代码、股票名称、策略、期末净值、收益率、交易次数
  - 支持日期快捷选择：近 1 个月、近 3 个月、近 6 个月、近 1 年、今年以来
  - `/api/summary` 支持缓存优先返回，减少首页阻塞

- **单票详情页**
  - 点击表格行进入单票回测详情
  - 支持推演式查看 K 线、买卖点和交易日志

- **配置管理页**
  - 股票池支持多行批量编辑
  - 支持格式化、导出、粘贴后自动整理
  - 策略可在 `dual_ma`、`bollinger_bands`、`rsi_reversal` 间切换

- **妙想工具箱**
  - 资讯搜索
  - 金融数据查询
  - 智能选股
  - 模拟组合查询

- **数据与缓存**
  - 本地 Parquet 缓存
  - 支持 Tushare HTTP 代理
  - 数据抓取失败时有重试和回退机制

## 技术栈

- **后端**：Python 3、FastAPI、Pandas、AKShare、Uvicorn
- **前端**：Vue 3、Vite、Element Plus、Axios、Dayjs
- **数据存储**：本地 Parquet 缓存

## 快速开始

### 1. 克隆仓库

```bash
git clone git@github.com:weifu1997/QuantSandbox.git
cd QuantSandbox
```

### 2. 启动后端

先创建虚拟环境并安装依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> 注意：项目使用本地 Parquet 缓存，`requirements.txt` 中已包含 `pyarrow`；如果缺少该依赖，`/api/summary` 等命中缓存读取路径的接口会因 `pandas.read_parquet()` 无可用引擎而报错。

推荐使用项目自带脚本：

```bash
./scripts/backend_ctl.sh start
./scripts/backend_ctl.sh status
./scripts/backend_ctl.sh doctor
./scripts/backend_ctl.sh logs
./scripts/backend_ctl.sh stop
```

也可以手动启动：

```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

默认访问：`http://127.0.0.1:5173`

## 配置说明

项目根目录的 `config.yaml` 控制回测与数据源配置，主要包括：

- `account`：账户资金、佣金、印花税
- `stock_pool`：股票池
- `strategy`：当前策略名称与参数
- `data_source.tushare`：Tushare HTTP 代理配置

### 示例配置

```yaml
account:
  initial_cash: 15000.0
  commission_rate: 0.00025
  tax_rate: 0.0005

stock_pool:
  - sh600901
  - sz000883
  - sh601033
  - sh601598
  - sh600098
  - sz002091
  - sh600177
  - sz000543
  - sh600795

strategy:
  name: target_weight_demo
  parameters:
    rsi_period: 7
    max_target_weight: 0.3
    oversold_floor: 30
    overbought_ceiling: 70
    rebalance_threshold: 0.03

data_source:
  tushare:
    enabled: false
    base_url: https://tushare.data.godscode.com.cn/
    token: YOUR_TUSHARE_TOKEN_HERE
```

## 使用提示

- 不要把真实 token 提交到 GitHub
- 首次使用新股票代码时，可能需要联网抓取数据
- 若数据源请求过慢，首页总览会优先返回缓存结果

## 免责声明

本项目仅用于学习、研究与模拟交易演练，不构成任何投资建议。
