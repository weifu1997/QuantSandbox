<template>
  <div class="mx-page">
    <el-card class="hero-card">
      <div class="hero-top">
        <div>
          <div class="hero-title">妙想工具箱</div>
          <div class="hero-sub">mx-data / mx-xuangu / mx-moni 一体入口</div>
        </div>
        <div class="hero-actions">
          <el-button @click="$router.push('/')">返回首页</el-button>
        </div>
      </div>
    </el-card>

    <el-card class="main-card">
      <el-tabs v-model="activeTab" type="border-card" class="mx-tabs">
        <el-tab-pane label="妙想资讯搜索" name="search">
          <el-card shadow="never" class="query-card">
            <template #header>
              <div class="card-header-inline">
                <span>资讯搜索</span>
                <span class="muted">新闻、公告、研报、政策、事件检索</span>
              </div>
            </template>
            <div class="query-row">
              <el-input
                v-model="searchQuery"
                placeholder="例如：贵州茅台最新公告"
                clearable
                @keyup.enter="runSearch"
              />
              <el-button type="primary" :loading="loading.search" @click="runSearch">查询</el-button>
            </div>
          </el-card>

          <el-row :gutter="12" class="result-row">
            <el-col :span="24">
              <el-card shadow="never" class="result-card">
                <template #header>查询摘要</template>
                <el-descriptions :column="3" border size="small">
                  <el-descriptions-item label="状态">{{ searchMeta.status || '暂无' }}</el-descriptions-item>
                  <el-descriptions-item label="输出目录">{{ searchMeta.output_dir || '暂无' }}</el-descriptions-item>
                  <el-descriptions-item label="返回码">{{ searchMeta.returncode ?? '暂无' }}</el-descriptions-item>
                </el-descriptions>
              </el-card>
            </el-col>
          </el-row>

          <el-row :gutter="12" class="result-row">
            <el-col :span="24">
              <el-card shadow="never" class="result-card">
                <template #header>运行输出</template>
                <pre class="search-output">{{ searchStdout || '暂无结果' }}</pre>
              </el-card>
            </el-col>
          </el-row>

          <el-collapse class="raw-collapse">
            <el-collapse-item title="查看原始 JSON" name="search-raw">
              <pre>{{ searchJsonText || '暂无结果' }}</pre>
            </el-collapse-item>
          </el-collapse>
        </el-tab-pane>

        <el-tab-pane label="妙想金融数据" name="data">
          <el-card shadow="never" class="query-card">
            <template #header>
              <div class="card-header-inline">
                <span>金融数据查询</span>
                <span class="muted">查询最新价、财务指标、行业数据等</span>
              </div>
            </template>
            <div class="query-row">
              <el-input
                v-model="dataQuery"
                placeholder="例如：东方财富最新价"
                clearable
                @keyup.enter="runData"
              />
              <el-button type="primary" :loading="loading.data" @click="runData">查询</el-button>
            </div>
          </el-card>

          <el-row :gutter="12" class="result-row">
            <el-col :span="24">
              <el-card shadow="never" class="result-card">
                <template #header>查询摘要</template>
                <el-descriptions :column="3" border size="small">
                  <el-descriptions-item label="状态">{{ dataMeta.status || '暂无' }}</el-descriptions-item>
                  <el-descriptions-item label="输出目录">{{ dataMeta.output_dir || '暂无' }}</el-descriptions-item>
                  <el-descriptions-item label="返回码">{{ dataMeta.returncode ?? '暂无' }}</el-descriptions-item>
                </el-descriptions>
              </el-card>
            </el-col>
          </el-row>

          <el-row :gutter="12" class="result-row">
            <el-col :span="24">
              <el-card shadow="never" class="result-card">
                <template #header>运行输出</template>
                <pre class="data-output">{{ dataStdout || '暂无结果' }}</pre>
              </el-card>
            </el-col>
          </el-row>

          <el-collapse class="raw-collapse">
            <el-collapse-item title="查看原始 JSON" name="data-raw">
              <pre>{{ dataJsonText || '暂无结果' }}</pre>
            </el-collapse-item>
          </el-collapse>
        </el-tab-pane>

        <el-tab-pane label="妙想智能选股" name="xuangu">
          <el-card shadow="never" class="query-card">
            <template #header>
              <div class="card-header-inline">
                <span>智能选股</span>
                <span class="muted">按市盈率、行业、财务条件筛选股票</span>
              </div>
            </template>
            <div class="query-row">
              <el-input
                v-model="xuanguQuery"
                placeholder="正常交易 非ST 非停牌 排除科创板 排除创业板 排除北交所..."
                clearable
                @keyup.enter="runXuangu"
              />
              <el-button type="primary" :loading="loading.xuangu" @click="runXuangu">查询</el-button>
            </div>
          </el-card>

          <el-row :gutter="12" class="result-row">
            <el-col :span="8">
              <el-card shadow="never" class="result-card">
                <template #header>结果概览</template>
                <el-descriptions :column="1" border size="small">
                  <el-descriptions-item label="股票数">{{ xuanguSummary.securityCount ?? '暂无' }}</el-descriptions-item>
                  <el-descriptions-item label="表格总数">{{ xuanguSummary.total ?? '暂无' }}</el-descriptions-item>
                  <el-descriptions-item label="条件数">{{ xuanguSummary.conditions.length || '暂无' }}</el-descriptions-item>
                </el-descriptions>
              </el-card>
            </el-col>
            <el-col :span="16">
              <el-card shadow="never" class="result-card">
                <template #header>
                  <div class="card-header-inline">
                    <span>筛选条件</span>
                    <span class="muted">{{ xuanguSummary.totalCondition || '暂无' }}</span>
                  </div>
                </template>
                <div class="tag-wrap" v-if="xuanguSummary.conditions.length">
                  <el-tag
                    v-for="(cond, idx) in xuanguSummary.conditions"
                    :key="idx"
                    type="info"
                    effect="light"
                    class="cond-tag"
                  >
                    {{ cond.describe }} · {{ cond.stockCount }}
                  </el-tag>
                </div>
                <div v-else class="empty-tip">暂无条件信息</div>
              </el-card>
            </el-col>
          </el-row>

          <el-card shadow="never" class="result-card table-card">
            <template #header>
              <div class="card-header-inline">
                <span>选股结果表</span>
                <span class="muted">共 {{ xuanguSummary.total ?? xuanguRows.length }} 行（当前展示 {{ xuanguRows.length }} 行）</span>
              </div>
            </template>
            <div class="table-action-row">
              <el-button type="primary" plain :disabled="!xuanguRows.length" @click="addXuanguToStockPool">
                一键加入股票池
              </el-button>
            </div>
            <el-table
              :data="xuanguRows"
              border
              stripe
              height="620"
              size="small"
              style="width: 100%"
              v-loading="loading.xuangu"
              empty-text="暂无结果"
            >
              <el-table-column type="index" width="60" fixed />
              <el-table-column
                v-for="col in xuanguColumns"
                :key="col.prop"
                :prop="col.prop"
                :label="col.label"
                :min-width="col.minWidth"
                show-overflow-tooltip
              />
            </el-table>
          </el-card>

          <el-collapse class="raw-collapse">
            <el-collapse-item title="查看原始 JSON" name="xuangu-raw">
              <pre>{{ xuanguJsonText || '暂无结果' }}</pre>
            </el-collapse-item>
          </el-collapse>
        </el-tab-pane>

        <el-tab-pane label="妙想模拟组合" name="moni">
          <el-card shadow="never" class="query-card">
            <template #header>
              <div class="card-header-inline">
                <span>模拟组合查询</span>
                <span class="muted">不需要输入框，直接点下面三个按钮</span>
              </div>
            </template>
            <div class="button-row">
              <el-button type="primary" :loading="loading.moni" @click="runMoni('我的资金')">我的资金</el-button>
              <el-button type="primary" :loading="loading.moni" @click="runMoni('我的持仓')">我的持仓</el-button>
              <el-button type="primary" :loading="loading.moni" @click="runMoni('我的委托')">我的委托</el-button>
            </div>
          </el-card>

          <el-row :gutter="12" class="result-row">
            <el-col :span="6">
              <el-card shadow="never" class="metric-card">
                <div class="metric-label">总资产</div>
                <div class="metric-value">{{ formatNumber(moniSummary.totalAssets) }}</div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="never" class="metric-card">
                <div class="metric-label">可用资金</div>
                <div class="metric-value">{{ formatNumber(moniSummary.availBalance) }}</div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="never" class="metric-card">
                <div class="metric-label">持仓市值</div>
                <div class="metric-value">{{ formatNumber(moniSummary.totalPosValue) }}</div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="never" class="metric-card">
                <div class="metric-label">持仓数</div>
                <div class="metric-value">{{ moniSummary.posCount ?? 0 }}</div>
              </el-card>
            </el-col>
          </el-row>

          <el-card shadow="never" class="result-card table-card" v-if="moniPositions.length">
            <template #header>
              <div class="card-header-inline">
                <span>持仓明细</span>
                <span class="muted">{{ moniPositions.length ? `共 ${moniPositions.length} 条` : '暂无持仓' }}</span>
              </div>
            </template>
            <el-table
              :data="moniPositions"
              border
              stripe
              size="small"
              style="width: 100%"
              empty-text="暂无持仓"
            >
              <el-table-column prop="stockCode" label="代码" min-width="110" />
              <el-table-column prop="stockName" label="名称" min-width="120" />
              <el-table-column prop="marketValue" label="市值" min-width="120" />
              <el-table-column prop="profit" label="浮动盈亏" min-width="120" />
              <el-table-column prop="availableQty" label="可用数量" min-width="100" />
              <el-table-column prop="qty" label="持仓数量" min-width="100" />
            </el-table>
          </el-card>

          <el-card shadow="never" class="result-card table-card" v-if="moniOrders.length">
            <template #header>
              <div class="card-header-inline">
                <span>委托明细</span>
                <span class="muted">{{ moniOrders.length ? `共 ${moniOrders.length} 条` : '暂无委托' }}</span>
              </div>
            </template>
            <el-table
              :data="moniOrders"
              border
              stripe
              size="small"
              style="width: 100%"
              empty-text="暂无委托"
            >
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
              <pre>{{ moniJsonText || '暂无结果' }}</pre>
            </el-collapse-item>
          </el-collapse>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import api from '../api';

const router = useRouter();
const props = defineProps({
  initialTab: { type: String, default: 'data' },
});

const activeTab = ref(props.initialTab || 'search');
watch(() => props.initialTab, (val) => {
  if (val) activeTab.value = val;
});

const searchQuery = ref('贵州茅台最新公告');
const dataQuery = ref('东方财富最新价');
const xuanguQuery = ref('正常交易 非ST 非停牌 排除科创板 排除创业板 排除北交所 股价3元到35元 市净率PB大于0.5 小于1.5 市盈率TTM大于5 小于20 股息率大于3% 最近60日涨幅大于-8% 小于10% 日均成交额大于5000万 股价站在250 日均线（年线）上方 近 60 日振幅：≤30% 无大额质押、无证监会立案调查、无业绩预亏预警 非银行');

const loading = reactive({ search: false, data: false, xuangu: false, moni: false });

const searchStdout = ref('');
const searchJsonText = ref('');
const searchMeta = reactive({ status: '', output_dir: '', returncode: null });

const dataStdout = ref('');
const dataJsonText = ref('');
const dataMeta = reactive({ status: '', output_dir: '', returncode: null });

const xuanguJsonText = ref('');
const xuanguColumns = ref([]);
const xuanguRows = ref([]);
const xuanguSummary = reactive({
  securityCount: null,
  total: null,
  totalCondition: '',
  conditions: [],
});

const moniJsonText = ref('');
const moniSummary = reactive({
  totalAssets: null,
  availBalance: null,
  totalPosValue: null,
  posCount: 0,
});
const moniPositions = ref([]);
const moniOrders = ref([]);
const MONI_CACHE_KEY = 'quantsandbox:mx-moni:last-success';

const loadMoniCache = () => {
  try {
    const cached = localStorage.getItem(MONI_CACHE_KEY);
    if (!cached) return false;
    const parsed = JSON.parse(cached);
    if (!parsed || typeof parsed !== 'object') return false;
    moniJsonText.value = parsed.moniJsonText || '';
    moniSummary.totalAssets = parsed.summary?.totalAssets ?? null;
    moniSummary.availBalance = parsed.summary?.availBalance ?? null;
    moniSummary.totalPosValue = parsed.summary?.totalPosValue ?? null;
    moniSummary.posCount = parsed.summary?.posCount ?? 0;
    moniPositions.value = Array.isArray(parsed.positions) ? parsed.positions : [];
    moniOrders.value = Array.isArray(parsed.orders) ? parsed.orders : [];
    return true;
  } catch (e) {
    console.warn('读取 mx-moni 缓存失败', e);
    return false;
  }
};

const saveMoniCache = () => {
  try {
    localStorage.setItem(MONI_CACHE_KEY, JSON.stringify({
      moniJsonText: moniJsonText.value,
      summary: {
        totalAssets: moniSummary.totalAssets,
        availBalance: moniSummary.availBalance,
        totalPosValue: moniSummary.totalPosValue,
        posCount: moniSummary.posCount,
      },
      positions: moniPositions.value,
      orders: moniOrders.value,
      savedAt: Date.now(),
    }));
  } catch (e) {
    console.warn('写入 mx-moni 缓存失败', e);
  }
};

const parseText = (value) => {
  if (value === null || value === undefined) return '';
  if (Array.isArray(value)) return value.map(parseText).filter(Boolean).join('、');
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
};

const formatNumber = (value) => {
  if (value === null || value === undefined || value === '') return '暂无';
  const num = Number(value);
  if (Number.isNaN(num)) return String(value);
  return num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

const extractXuangu = (rawJson) => {
  const result = rawJson?.data?.data?.allResults?.result || rawJson?.data?.data?.result || {};
  const columns = Array.isArray(result.columns) ? result.columns : [];
  const dataList = Array.isArray(result.dataList) ? result.dataList : [];

  xuanguColumns.value = columns.map((col, index) => ({
    prop: `c_${index}`,
    label: col.title || col.key || `列${index + 1}`,
    minWidth: index === 0 ? 70 : 120,
  }));

  xuanguRows.value = dataList.map((row) => {
    const item = {};
    columns.forEach((col, index) => {
      const value = parseText(row?.[col.key]);
      item[`c_${index}`] = value;
      const title = String(col.title || col.key || '');
      if (!item._stockCode && /代码|code/i.test(title)) {
        item._stockCode = value;
      }
    });
    return item;
  });

  xuanguSummary.securityCount = rawJson?.data?.data?.securityCount ?? xuanguRows.value.length;
  xuanguSummary.total = result.total ?? result.totalRecordCount ?? xuanguRows.value.length;
  xuanguSummary.totalCondition = rawJson?.data?.data?.totalCondition || '';
  xuanguSummary.conditions = Array.isArray(rawJson?.data?.data?.responseConditionList)
    ? rawJson.data.data.responseConditionList
    : [];
};

const statusTextMap = {
  0: '待处理',
  1: '已申报',
  2: '部成',
  3: '部撤',
  4: '已成',
  5: '待撤',
  6: '已撤',
  7: '废单',
  8: '已报',
  9: '已拒绝',
  200: '成功',
  204: '失败',
};

const extractMoni = (rawJson) => {
  const accountRoot = rawJson?.data?.data || rawJson?.data || {};
  const account = accountRoot.result && typeof accountRoot.result === 'object' ? accountRoot : accountRoot;
  moniSummary.totalAssets = account.totalAssets ?? account.balanceActual ?? null;
  moniSummary.availBalance = account.availBalance ?? null;
  moniSummary.totalPosValue = account.totalPosValue ?? null;
  moniSummary.posCount = account.posCount ?? (Array.isArray(account.posList) ? account.posList.length : 0);
  moniPositions.value = Array.isArray(account.posList)
    ? account.posList.map((pos) => ({
        stockCode: pos.stockCode || pos.secCode || pos.securityCode || '',
        stockName: pos.stockName || pos.secName || pos.securityName || '',
        marketValue: formatNumber(pos.marketValue ?? pos.stockValue ?? pos.currentValue ?? pos.marketVal),
        profit: formatNumber(pos.profit ?? pos.floatProfit ?? pos.floatProfitLoss ?? pos.unrealizedPnl),
        availableQty: pos.availableQty ?? pos.availableVol ?? pos.canSellQty ?? pos.canUseQty ?? '',
        qty: pos.qty ?? pos.volume ?? pos.holdQty ?? pos.totalQty ?? '',
      }))
    : [];

  const orders = Array.isArray(account.orders)
    ? account.orders
    : Array.isArray(account.orderList)
      ? account.orderList
      : [];
  moniOrders.value = orders.map((order) => ({
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
  moniJsonText.value = resData.raw_json ? JSON.stringify(resData.raw_json, null, 2) : '';
  extractMoni(resData.raw_json || {});
};

const hasMoniData = () => {
  return Boolean(
    String(moniSummary.totalAssets ?? '') !== '' ||
    String(moniSummary.availBalance ?? '') !== '' ||
    String(moniSummary.totalPosValue ?? '') !== '' ||
    (moniSummary.posCount ?? 0) > 0 ||
    moniPositions.value.length ||
    moniOrders.value.length,
  );
};

const normalizeStockCode = (code) => {
  const value = String(code || '').trim();
  if (!value) return '';
  if (/^(sh|sz|bj)\d{6}$/i.test(value)) return value.toLowerCase();
  if (/^\d{6}$/.test(value)) {
    if (/^(60|68)/.test(value)) return `sh${value}`;
    if (/^8/.test(value)) return `bj${value}`;
    return `sz${value}`;
  }
  return '';
};

const addXuanguToStockPool = async () => {
  const rawRows = Array.isArray(xuanguRows.value) ? xuanguRows.value : [];
  const codes = [];
  for (const row of rawRows) {
    const rawCode = row?._stockCode || '';
    const code = normalizeStockCode(rawCode);
    if (code) codes.push(code);
  }

  const uniqueCodes = [...new Set(codes)];
  if (!uniqueCodes.length) {
    ElMessage.warning('当前结果里没有可识别的股票代码');
    return;
  }

  try {
    const res = await api.get('/config');
    const currentPool = Array.isArray(res.data.stock_pool) ? res.data.stock_pool.map(normalizeStockCode).filter(Boolean) : [];
    const merged = [...new Set([...currentPool, ...uniqueCodes])];
    const updateRes = await api.post('/config', { stock_pool: merged });
    if (updateRes.data?.status === 'success' || updateRes.status === 200) {
      ElMessage.success(`已加入股票池 ${uniqueCodes.length} 只，已自动去重`);
      router.push('/config');
    } else {
      ElMessage.success(`已尝试加入股票池 ${uniqueCodes.length} 只`);
      router.push('/config');
    }
  } catch (e) {
    ElMessage.error('加入股票池失败');
    console.error(e);
  }
};

const runSearch = async () => {
  const q = searchQuery.value.trim();
  if (!q) return ElMessage.warning('请输入查询内容');
  loading.search = true;
  try {
    const res = await api.post('/mx/search', { query: q });
    searchStdout.value = res.data.stdout || '';
    searchJsonText.value = res.data.raw_json ? JSON.stringify(res.data.raw_json, null, 2) : '';
    searchMeta.status = res.data.status || '';
    searchMeta.output_dir = res.data.output_dir || '';
    searchMeta.returncode = res.data.returncode ?? null;
    ElMessage.success('查询成功');
  } catch (e) {
    ElMessage.error('妙想资讯搜索失败');
    console.error(e);
  } finally {
    loading.search = false;
  }
};

const runData = async () => {
  const q = dataQuery.value.trim();
  if (!q) return ElMessage.warning('请输入查询内容');
  loading.data = true;
  try {
    const res = await api.post('/mx/data', { query: q });
    dataStdout.value = res.data.stdout || '';
    dataJsonText.value = res.data.raw_json ? JSON.stringify(res.data.raw_json, null, 2) : '';
    dataMeta.status = res.data.status || '';
    dataMeta.output_dir = res.data.output_dir || '';
    dataMeta.returncode = res.data.returncode ?? null;
    ElMessage.success('查询成功');
  } catch (e) {
    ElMessage.error('妙想数据查询失败');
    console.error(e);
  } finally {
    loading.data = false;
  }
};

const runXuangu = async () => {
  const q = xuanguQuery.value.trim();
  if (!q) return ElMessage.warning('请输入查询内容');
  loading.xuangu = true;
  try {
    const res = await api.post('/mx/xuangu', { query: q });
    xuanguJsonText.value = res.data.raw_json ? JSON.stringify(res.data.raw_json, null, 2) : '';
    extractXuangu(res.data.raw_json || {});
    ElMessage.success('查询成功');
  } catch (e) {
    ElMessage.error('妙想选股查询失败');
    console.error(e);
  } finally {
    loading.xuangu = false;
  }
};

const runMoni = async (query) => {
  loading.moni = true;
  try {
    const res = await api.post('/mx/moni', { query });
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
    if (loadMoniCache()) {
      ElMessage.warning('接口查询失败，已回退到上次缓存');
    } else {
      ElMessage.error('妙想模拟组合查询失败');
    }
    console.error(e);
  } finally {
    loading.moni = false;
  }
};

onMounted(() => {
  loadMoniCache();
});
</script>

<style scoped>
.mx-page { padding: 20px; max-width: 1600px; margin: 0 auto; background: #0b0e14; min-height: calc(100vh - 60px); color: #d1d4dc; }
.hero-card,
.main-card,
.query-card,
.result-card,
.metric-card { background: #131722; border: 1px solid #2b3139; border-radius: 12px; }
.hero-card { margin-bottom: 16px; }
.hero-top { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.hero-title { font-size: 22px; font-weight: 700; color: #fff; }
.hero-sub { margin-top: 4px; color: #8a919e; font-size: 13px; }
.main-card { padding: 0; }
.mx-tabs :deep(.el-tabs__content) { padding: 16px; background: #131722; }
.mx-tabs :deep(.el-tabs__item) { color: #d1d4dc; }
.mx-tabs :deep(.el-tabs__item.is-active) { color: #fff; }
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
.tag-wrap { display: flex; flex-wrap: wrap; gap: 8px; }
.cond-tag { max-width: 100%; }
.empty-tip { color: #8a919e; padding: 8px 0; }
.query-row,
.button-row { display: flex; gap: 12px; align-items: center; }
.query-row :deep(.el-input) { flex: 1; }
:deep(.el-input__wrapper) { background: #0f131a !important; box-shadow: 0 0 0 1px #3b4351 inset !important; }
:deep(.el-input__inner) { color: #eef2f7 !important; }
:deep(.el-input__inner::placeholder) { color: #8a919e !important; }
:deep(.el-button--primary) { background: #0ECB81; border-color: #0ECB81; color: #08110d; font-weight: 600; }
:deep(.el-button--primary:hover), :deep(.el-button--primary:focus) { background: #19d08d; border-color: #19d08d; color: #08110d; }
pre { white-space: pre-wrap; word-break: break-word; margin: 0; min-height: 220px; color: #eef2f7; background: #0f131a; border: 1px solid #2b3139; border-radius: 8px; padding: 12px; }
.search-output { min-height: 360px; line-height: 1.65; }
.data-output { min-height: 320px; line-height: 1.65; }
.raw-collapse { margin-top: 12px; }
:deep(.el-collapse-item__header) { background: #131722; color: #eef2f7; border: 1px solid #2b3139; }
:deep(.el-collapse-item__wrap) { background: #131722; border: 1px solid #2b3139; }
:deep(.el-card__body) { background: #131722; color: #eef2f7; }
:deep(.el-card__header) { background: #131722; border-bottom: 1px solid #2b3139; color: #eef2f7; }
:deep(.el-descriptions) { background: #131722 !important; color: #eef2f7 !important; }
:deep(.el-table) { background: #1a1e29 !important; --el-table-tr-bg-color: #1a1e29; --el-table-header-bg-color: #1a1e29; --el-table-border-color: #2b3139; --el-table-row-hover-bg-color: #222836; --el-table-text-color: #eef2f7; --el-table-header-text-color: #aeb6c2; }
:deep(.el-table th.el-table__cell), :deep(.el-table td.el-table__cell) { background: #1a1e29 !important; color: #eef2f7 !important; }
:deep(.el-table .cell) { color: #eef2f7 !important; }
:deep(.el-table .el-table__header-wrapper), :deep(.el-table .el-table__body-wrapper), :deep(.el-table .el-table__fixed), :deep(.el-table .el-table__fixed-right), :deep(.el-table__inner-wrapper), :deep(.el-table__inner-wrapper::before), :deep(.el-scrollbar), :deep(.el-scrollbar__wrap), :deep(.el-scrollbar__view) { background: #1a1e29 !important; }
:deep(.el-table .el-table__body .el-table__row td), :deep(.el-table .el-table__body .el-table__row > td) { background: #1a1e29 !important; color: #eef2f7 !important; }
:deep(.el-table .el-table__body .el-table__row:hover > td) { background: #222836 !important; }
:deep(.el-table__empty-block), :deep(.el-table__empty-text) { background: #1a1e29 !important; color: #8a919e !important; }
:deep(.el-descriptions__body) { background: #131722 !important; color: #eef2f7 !important; border-color: #2b3139 !important; }
:deep(.el-descriptions__label) { background: #1a1e29 !important; color: #aeb6c2 !important; border-color: #2b3139 !important; }
:deep(.el-descriptions__content) { background: #131722 !important; color: #eef2f7 !important; border-color: #2b3139 !important; }
:deep(.el-table) { background: #1a1e29 !important; --el-table-tr-bg-color: #1a1e29; --el-table-header-bg-color: #1a1e29; --el-table-border-color: #2b3139; --el-table-row-hover-bg-color: #222836; --el-table-text-color: #eef2f7; --el-table-header-text-color: #aeb6c2; }
:deep(.el-table th.el-table__cell), :deep(.el-table td.el-table__cell) { background: #1a1e29 !important; color: #eef2f7 !important; }
:deep(.el-table .cell) { color: #eef2f7 !important; }
:deep(.el-table .el-table__header-wrapper), :deep(.el-table .el-table__body-wrapper), :deep(.el-table .el-table__fixed), :deep(.el-table .el-table__fixed-right), :deep(.el-table__inner-wrapper), :deep(.el-table__inner-wrapper::before), :deep(.el-scrollbar), :deep(.el-scrollbar__wrap), :deep(.el-scrollbar__view) { background: #1a1e29 !important; }
:deep(.el-table .el-table__body .el-table__row td), :deep(.el-table .el-table__body .el-table__row > td) { background: #1a1e29 !important; color: #eef2f7 !important; }
:deep(.el-table .el-table__body .el-table__row:hover > td) { background: #222836 !important; }
:deep(.el-table__empty-block), :deep(.el-table__empty-text) { background: #1a1e29 !important; color: #8a919e !important; }
:deep(.el-tabs--border-card) { background: #131722; border: 1px solid #2b3139; }
:deep(.el-tabs--border-card > .el-tabs__header) { background: #131722; border-bottom: 1px solid #2b3139; }
:deep(.el-tabs--border-card > .el-tabs__header .el-tabs__item) { color: #d1d4dc; border-color: #2b3139; }
:deep(.el-tabs--border-card > .el-tabs__header .el-tabs__item.is-active) { background: #1a1e29; color: #fff; }
</style>
