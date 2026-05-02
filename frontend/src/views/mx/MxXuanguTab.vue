<template>
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
      <el-button type="primary" :loading="loading" @click="runXuangu">查询</el-button>
    </div>
  </el-card>

  <el-row :gutter="12" class="result-row">
    <el-col :span="8">
      <el-card shadow="never" class="result-card">
        <template #header>结果概览</template>
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="股票数">{{ summary.securityCount ?? '暂无' }}</el-descriptions-item>
          <el-descriptions-item label="表格总数">{{ summary.total ?? '暂无' }}</el-descriptions-item>
          <el-descriptions-item label="条件数">{{ summary.conditions.length || '暂无' }}</el-descriptions-item>
        </el-descriptions>
      </el-card>
    </el-col>
    <el-col :span="16">
      <el-card shadow="never" class="result-card">
        <template #header>
          <div class="card-header-inline">
            <span>筛选条件</span>
            <span class="muted">{{ summary.totalCondition || '暂无' }}</span>
          </div>
        </template>
        <div class="tag-wrap" v-if="summary.conditions.length">
          <el-tag
            v-for="(cond, idx) in summary.conditions"
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
        <span class="muted">共 {{ summary.total ?? rows.length }} 行（当前展示 {{ rows.length }} 行）</span>
      </div>
    </template>
    <div class="table-action-row">
      <el-button type="primary" plain :disabled="!rows.length" @click="addToStockPool">
        一键加入股票池
      </el-button>
    </div>
    <el-table
      :data="rows"
      border
      stripe
      height="620"
      size="small"
      style="width: 100%"
      v-loading="loading"
      empty-text="暂无结果"
    >
      <el-table-column type="index" width="60" fixed />
      <el-table-column
        v-for="col in columns"
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
      <pre>{{ jsonText || '暂无结果' }}</pre>
    </el-collapse-item>
  </el-collapse>
</template>

<script setup>
import { reactive, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import api from '../../api';

const router = useRouter();
const props = defineProps({
  initialQuery: { type: String, default: '正常交易 非ST 非停牌 排除科创板 排除创业板 排除北交所 股价3元到35元 市净率PB大于0.5 小于1.5 市盈率TTM大于5 小于20 股息率大于3% 最近60日涨幅大于-8% 小于10% 日均成交额大于5000万 股价站在250 日均线（年线）上方 近 60 日振幅：≤30% 无大额质押、无证监会立案调查、无业绩预亏预警 非银行' },
});

const xuanguQuery = ref(props.initialQuery);
watch(() => props.initialQuery, (val) => {
  if (val) xuanguQuery.value = val;
});

const loading = ref(false);
const jsonText = ref('');
const columns = ref([]);
const rows = ref([]);
const summary = reactive({ securityCount: null, total: null, totalCondition: '', conditions: [] });

const parseText = (value) => {
  if (value === null || value === undefined) return '';
  if (Array.isArray(value)) return value.map(parseText).filter(Boolean).join('、');
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
};

const extractXuangu = (rawJson) => {
  const result = rawJson?.data?.data?.allResults?.result || rawJson?.data?.data?.result || {};
  const cols = Array.isArray(result.columns) ? result.columns : [];
  const dataList = Array.isArray(result.dataList) ? result.dataList : [];

  columns.value = cols.map((col, index) => ({
    prop: `c_${index}`,
    label: col.title || col.key || `列${index + 1}`,
    minWidth: index === 0 ? 70 : 120,
  }));

  rows.value = dataList.map((row) => {
    const item = {};
    cols.forEach((col, index) => {
      const value = parseText(row?.[col.key]);
      item[`c_${index}`] = value;
      const title = String(col.title || col.key || '');
      if (!item._stockCode && /代码|code/i.test(title)) item._stockCode = value;
    });
    return item;
  });

  summary.securityCount = rawJson?.data?.data?.securityCount ?? rows.value.length;
  summary.total = result.total ?? result.totalRecordCount ?? rows.value.length;
  summary.totalCondition = rawJson?.data?.data?.totalCondition || '';
  summary.conditions = Array.isArray(rawJson?.data?.data?.responseConditionList) ? rawJson.data.data.responseConditionList : [];
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

const addToStockPool = async () => {
  const rawRows = Array.isArray(rows.value) ? rows.value : [];
  const codes = [];
  for (const row of rawRows) {
    const code = normalizeStockCode(row?._stockCode || '');
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

const runXuangu = async () => {
  const q = xuanguQuery.value.trim();
  if (!q) return ElMessage.warning('请输入查询内容');
  loading.value = true;
  try {
    const res = await api.post('/mx/xuangu', { query: q });
    jsonText.value = res.data.raw_json ? JSON.stringify(res.data.raw_json, null, 2) : '';
    extractXuangu(res.data.raw_json || {});
    ElMessage.success('查询成功');
  } catch (e) {
    ElMessage.error('妙想选股查询失败');
    console.error(e);
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.query-card { margin-bottom: 16px; }
.result-row { margin-bottom: 12px; }
.result-card { background: #1a1e29; color: #d1d4dc; }
.table-card { margin-bottom: 12px; }
.table-action-row { display: flex; justify-content: flex-end; margin-bottom: 12px; }
.card-header-inline { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.muted { color: #8a919e; font-size: 12px; }
.tag-wrap { display: flex; flex-wrap: wrap; gap: 8px; }
.cond-tag { max-width: 100%; }
.empty-tip { color: #8a919e; padding: 8px 0; }
.query-row { display: flex; gap: 12px; align-items: center; }
.query-row :deep(.el-input) { flex: 1; }
:deep(.el-input__wrapper) { background: #0f131a !important; box-shadow: 0 0 0 1px #3b4351 inset !important; }
:deep(.el-input__inner) { color: #eef2f7 !important; }
:deep(.el-input__inner::placeholder) { color: #8a919e !important; }
:deep(.el-button--primary) { background: #0ECB81; border-color: #0ECB81; color: #08110d; font-weight: 600; }
:deep(.el-button--primary:hover), :deep(.el-button--primary:focus) { background: #19d08d; border-color: #19d08d; color: #08110d; }
pre { white-space: pre-wrap; word-break: break-word; margin: 0; min-height: 220px; color: #eef2f7; background: #0f131a; border: 1px solid #2b3139; border-radius: 8px; padding: 12px; }
.raw-collapse { margin-top: 12px; }
:deep(.el-collapse-item__header) { background: #131722; color: #eef2f7; border: 1px solid #2b3139; }
:deep(.el-collapse-item__wrap) { background: #131722; border: 1px solid #2b3139; }
:deep(.el-card__body) { background: #131722; color: #eef2f7; }
:deep(.el-card__header) { background: #131722; border-bottom: 1px solid #2b3139; color: #eef2f7; }
:deep(.el-descriptions),
:deep(.el-descriptions__body),
:deep(.el-descriptions__table),
:deep(.el-descriptions__cell),
:deep(.el-descriptions__label),
:deep(.el-descriptions__content) { background: #131722 !important; color: #eef2f7 !important; border-color: #2b3139 !important; }
:deep(.el-table) { background: #1a1e29 !important; --el-table-tr-bg-color: #1a1e29; --el-table-header-bg-color: #1a1e29; --el-table-border-color: #2b3139; --el-table-row-hover-bg-color: #222836; --el-table-text-color: #eef2f7; --el-table-header-text-color: #aeb6c2; }
:deep(.el-table th.el-table__cell), :deep(.el-table td.el-table__cell) { background: #1a1e29 !important; color: #eef2f7 !important; }
:deep(.el-table .cell) { color: #eef2f7 !important; }
:deep(.el-table .el-table__header-wrapper), :deep(.el-table .el-table__body-wrapper), :deep(.el-table .el-table__fixed), :deep(.el-table .el-table__fixed-right), :deep(.el-table__inner-wrapper), :deep(.el-table__inner-wrapper::before), :deep(.el-scrollbar), :deep(.el-scrollbar__wrap), :deep(.el-scrollbar__view) { background: #1a1e29 !important; }
:deep(.el-table .el-table__body .el-table__row td), :deep(.el-table .el-table__body .el-table__row > td) { background: #1a1e29 !important; color: #eef2f7 !important; }
:deep(.el-table .el-table__body .el-table__row:hover > td) { background: #222836 !important; }
:deep(.el-table__empty-block), :deep(.el-table__empty-text) { background: #1a1e29 !important; color: #8a919e !important; }
</style>
