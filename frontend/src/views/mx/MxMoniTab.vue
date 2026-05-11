<template>
  <el-card shadow="never" class="query-card">
    <template #header>
      <div class="card-header-inline">
        <span>模拟组合查询</span>
        <span class="muted">不需要输入框，直接点下面三个按钮</span>
      </div>
    </template>
    <div class="button-row">
      <el-button type="primary" :loading="loading" @click="runMoni('我的资金')">我的资金</el-button>
      <el-button type="primary" :loading="loading" @click="runMoni('我的持仓')">我的持仓</el-button>
      <el-button type="primary" :loading="loading" @click="runMoni('我的委托')">我的委托</el-button>
    </div>
  </el-card>

  <el-row :gutter="12" class="result-row">
    <el-col :span="6">
      <el-card shadow="never" class="metric-card">
        <div class="metric-label">总资产</div>
        <div class="metric-value">{{ formatNumber(summary.totalAssets) }}</div>
      </el-card>
    </el-col>
    <el-col :span="6">
      <el-card shadow="never" class="metric-card">
        <div class="metric-label">可用资金</div>
        <div class="metric-value">{{ formatNumber(summary.availBalance) }}</div>
      </el-card>
    </el-col>
    <el-col :span="6">
      <el-card shadow="never" class="metric-card">
        <div class="metric-label">持仓市值</div>
        <div class="metric-value">{{ formatNumber(summary.totalPosValue) }}</div>
      </el-card>
    </el-col>
    <el-col :span="6">
      <el-card shadow="never" class="metric-card">
        <div class="metric-label">持仓数</div>
        <div class="metric-value">{{ summary.posCount ?? 0 }}</div>
      </el-card>
    </el-col>
  </el-row>

  <el-card shadow="never" class="result-card table-card" v-if="positions.length">
    <template #header>
      <div class="card-header-inline">
        <span>持仓明细</span>
        <span class="muted">{{ positions.length ? `共 ${positions.length} 条` : '暂无持仓' }}</span>
      </div>
    </template>
    <el-table :data="positions" border stripe size="small" style="width: 100%" empty-text="暂无持仓">
      <el-table-column prop="stockCode" label="代码" min-width="110" />
      <el-table-column prop="stockName" label="名称" min-width="120" />
      <el-table-column prop="marketValue" label="市值" min-width="120" />
      <el-table-column prop="profit" label="浮动盈亏" min-width="120" />
      <el-table-column prop="availableQty" label="可用数量" min-width="100" />
      <el-table-column prop="qty" label="持仓数量" min-width="100" />
    </el-table>
  </el-card>

  <el-card shadow="never" class="result-card table-card" v-if="orders.length">
    <template #header>
      <div class="card-header-inline">
        <span>委托明细</span>
        <span class="muted">{{ orders.length ? `共 ${orders.length} 条` : '暂无委托' }}</span>
      </div>
    </template>
    <el-table :data="orders" border stripe size="small" style="width: 100%" empty-text="暂无委托">
      <el-table-column prop="id" label="委托号" min-width="160" />
      <el-table-column prop="secCode" label="代码" min-width="100" />
      <el-table-column prop="secName" label="名称" min-width="120" />
      <el-table-column prop="statusText" label="状态" min-width="100" />
      <el-table-column prop="price" label="委托价" min-width="100" />
      <el-table-column prop="count" label="数量" min-width="100" />
      <el-table-column prop="tradeCount" label="成交数量" min-width="100" />
    </el-table>
  </el-card>

  <el-collapse class="raw-collapse">
    <el-collapse-item title="查看原始 JSON" name="moni-raw">
      <pre>{{ jsonText || '暂无结果' }}</pre>
    </el-collapse-item>
  </el-collapse>
</template>

<script setup>
import { onMounted, onUnmounted, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';
import api from '../../api';

const MONI_CACHE_KEY = 'quantsandbox:mx-moni:last-success';
const MONI_CACHE_TTL_MS = 5 * 60 * 1000;

const loading = ref(false);
const jsonText = ref('');
const summary = reactive({ totalAssets: null, availBalance: null, totalPosValue: null, posCount: 0 });
const positions = ref([]);
const orders = ref([]);
let activeController = null;

const statusTextMap = {
  0: '待处理', 1: '已申报', 2: '部成', 3: '部撤', 4: '已成', 5: '待撤', 6: '已撤', 7: '废单', 8: '已报', 9: '已拒绝', 200: '成功', 204: '失败',
};

const formatNumber = (value) => {
  if (value === null || value === undefined || value === '') return '暂无';
  const num = Number(value);
  if (Number.isNaN(num)) return String(value);
  return num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

const loadMoniCache = () => {
  try {
    const cached = localStorage.getItem(MONI_CACHE_KEY);
    if (!cached) return false;
    const parsed = JSON.parse(cached);
    if (!parsed || typeof parsed !== 'object') return false;
    const savedAt = Number(parsed.savedAt || 0);
    if (!savedAt || (Date.now() - savedAt) > MONI_CACHE_TTL_MS) {
      localStorage.removeItem(MONI_CACHE_KEY);
      return false;
    }
    jsonText.value = '';
    summary.totalAssets = parsed.summary?.totalAssets ?? null;
    summary.availBalance = parsed.summary?.availBalance ?? null;
    summary.totalPosValue = parsed.summary?.totalPosValue ?? null;
    summary.posCount = parsed.summary?.posCount ?? 0;
    positions.value = [];
    orders.value = [];
    return true;
  } catch (e) {
    console.warn('读取 mx-moni 缓存失败', e);
    return false;
  }
};

const saveMoniCache = () => {
  try {
    localStorage.setItem(MONI_CACHE_KEY, JSON.stringify({
      summary: {
        totalAssets: summary.totalAssets,
        availBalance: summary.availBalance,
        totalPosValue: summary.totalPosValue,
        posCount: summary.posCount,
      },
      savedAt: Date.now(),
    }));
  } catch (e) {
    console.warn('写入 mx-moni 缓存失败', e);
  }
};

const extractMoni = (rawJson) => {
  const accountRoot = rawJson?.data?.data || rawJson?.data || {};
  const account = accountRoot.result && typeof accountRoot.result === 'object' ? accountRoot : accountRoot;
  summary.totalAssets = account.totalAssets ?? account.balanceActual ?? null;
  summary.availBalance = account.availBalance ?? null;
  summary.totalPosValue = account.totalPosValue ?? null;
  summary.posCount = account.posCount ?? (Array.isArray(account.posList) ? account.posList.length : 0);
  positions.value = Array.isArray(account.posList)
    ? account.posList.map((pos) => ({
        stockCode: pos.stockCode || pos.secCode || pos.securityCode || '',
        stockName: pos.stockName || pos.secName || pos.securityName || '',
        marketValue: formatNumber(pos.marketValue ?? pos.stockValue ?? pos.currentValue ?? pos.marketVal),
        profit: formatNumber(pos.profit ?? pos.floatProfit ?? pos.floatProfitLoss ?? pos.unrealizedPnl),
        availableQty: pos.availableQty ?? pos.availableVol ?? pos.canSellQty ?? pos.canUseQty ?? pos.availCount ?? '',
        qty: pos.qty ?? pos.volume ?? pos.holdQty ?? pos.totalQty ?? pos.count ?? '',
      }))
    : [];

  const ordersList = Array.isArray(account.orders)
    ? account.orders
    : Array.isArray(account.orderList)
      ? account.orderList
      : [];
  orders.value = ordersList.map((order) => ({
    id: order.id || order.orderId || '',
    secCode: order.secCode || order.stockCode || '',
    secName: order.secName || order.stockName || '',
    statusText: statusTextMap[order.status] || statusTextMap[order.dbStatus] || String(order.status ?? order.dbStatus ?? ''),
    price: order.price !== undefined ? formatNumber(Number(order.price) / (order.priceDec === 3 ? 1000 : 100)) : '',
    count: order.count ?? order.orderQty ?? '',
    tradeCount: order.tradeCount ?? order.filledQty ?? '',
  }));
};

const applyMoniResponse = (resData) => {
  jsonText.value = resData.raw_json ? JSON.stringify(resData.raw_json, null, 2) : '';
  extractMoni(resData.raw_json || {});
};

const hasMoniData = () => Boolean(
  String(summary.totalAssets ?? '') !== '' ||
  String(summary.availBalance ?? '') !== '' ||
  String(summary.totalPosValue ?? '') !== '' ||
  (summary.posCount ?? 0) > 0 ||
  positions.value.length ||
  orders.value.length,
);

const runMoni = async (query) => {
  if (activeController) {
    activeController.abort();
  }
  const requestController = new AbortController();
  activeController = requestController;
  loading.value = true;
  try {
    const res = await api.post('/mx/moni', { query }, { signal: requestController.signal });
    if (activeController !== requestController) {
      return;
    }
    applyMoniResponse(res.data || {});
    if (hasMoniData()) {
      saveMoniCache();
      ElMessage.success('查询成功');
    } else if (loadMoniCache()) {
      ElMessage.info('接口暂无新数据，已展示上次缓存');
    } else {
      ElMessage.info('查询成功，但暂无可展示数据');
    }
  } catch (e) {
    if (e?.isCanceled || requestController.signal.aborted) {
      return;
    }
    if (activeController !== requestController) {
      return;
    }
    if (loadMoniCache()) {
      ElMessage.warning('接口查询失败，已回退到上次缓存');
    } else {
      ElMessage.error('妙想模拟组合查询失败');
    }
    console.error(e);
  } finally {
    if (activeController === requestController) {
      activeController = null;
      loading.value = false;
    }
  }
};

onMounted(() => {
  loadMoniCache();
});

onUnmounted(() => {
  if (activeController) {
    activeController.abort();
    activeController = null;
  }
});
</script>

<style scoped>
.query-card { margin-bottom: 16px; }
.result-row { margin-bottom: 12px; }
.result-card,
.metric-card { background: #1a1e29; color: #d1d4dc; }
.table-card { margin-bottom: 12px; }
.table-action-row { display: flex; justify-content: flex-end; margin-bottom: 12px; }
.metric-card { text-align: center; padding: 12px 8px; }
.metric-label { color: #8a919e; font-size: 12px; }
.metric-value { margin-top: 8px; font-size: 20px; font-weight: 700; color: #fff; }
.card-header-inline { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.muted { color: #8a919e; font-size: 12px; }
.query-row,
.button-row { display: flex; gap: 12px; align-items: center; }
pre { white-space: pre-wrap; word-break: break-word; margin: 0; min-height: 220px; color: #eef2f7; background: #0f131a; border: 1px solid #2b3139; border-radius: 8px; padding: 12px; }
.raw-collapse { margin-top: 12px; }
:deep(.el-collapse-item__header) { background: #131722; color: #eef2f7; border: 1px solid #2b3139; }
:deep(.el-collapse-item__wrap) { background: #131722; border: 1px solid #2b3139; }
:deep(.el-card__body) { background: #131722; color: #eef2f7; }
:deep(.el-card__header) { background: #131722; border-bottom: 1px solid #2b3139; color: #eef2f7; }
:deep(.el-table) { background: #1a1e29 !important; --el-table-tr-bg-color: #1a1e29; --el-table-header-bg-color: #1a1e29; --el-table-border-color: #2b3139; --el-table-row-hover-bg-color: #222836; --el-table-text-color: #eef2f7; --el-table-header-text-color: #aeb6c2; }
:deep(.el-table th.el-table__cell), :deep(.el-table td.el-table__cell) { background: #1a1e29 !important; color: #eef2f7 !important; }
:deep(.el-table .cell) { color: #eef2f7 !important; }
:deep(.el-table .el-table__header-wrapper), :deep(.el-table .el-table__body-wrapper), :deep(.el-table .el-table__fixed), :deep(.el-table .el-table__fixed-right), :deep(.el-table__inner-wrapper), :deep(.el-table__inner-wrapper::before), :deep(.el-scrollbar), :deep(.el-scrollbar__wrap), :deep(.el-scrollbar__view) { background: #1a1e29 !important; }
:deep(.el-table .el-table__body .el-table__row td), :deep(.el-table .el-table__body .el-table__row > td) { background: #1a1e29 !important; color: #eef2f7 !important; }
:deep(.el-table .el-table__body .el-table__row:hover > td) { background: #222836 !important; }
:deep(.el-table__empty-block), :deep(.el-table__empty-text) { background: #1a1e29 !important; color: #8a919e !important; }
</style>
