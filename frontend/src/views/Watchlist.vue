<template>
  <div class="watchlist-page">
    <el-card class="hero-card">
      <div class="hero-top">
        <div>
          <div class="hero-title">👁️ 观察池</div>
          <div class="hero-sub">所有工作流输出的入池观察标的</div>
        </div>
        <div class="hero-actions">
          <el-tag v-if="total > 0" type="success" size="large">{{ total }} 只标的</el-tag>
          <el-button @click="$router.push('/workflow')">🚀 启动扫描</el-button>
          <el-button @click="$router.push('/workflow/history')">🕘 历史记录</el-button>
          <el-button type="danger" @click="handleBatchDelete" :disabled="selectedRows.length === 0" :loading="deleting">
            删除选中 ({{ selectedRows.length }})
          </el-button>
        </div>
      </div>
    </el-card>

    <el-card class="filter-card">
      <div class="filter-bar">
        <el-input v-model="searchText" placeholder="搜索代码或名称..." clearable style="width: 240px" />
        <el-select v-model="riskFilter" placeholder="风险等级" clearable style="width: 140px">
          <el-option label="低风险" value="low" />
          <el-option label="中风险" value="medium" />
          <el-option label="高风险" value="high" />
        </el-select>
        <el-radio-group v-model="watchlistView" size="small" class="view-toggle">
          <el-radio-button label="latest">当前视图</el-radio-button>
          <el-radio-button label="all">全部历史</el-radio-button>
        </el-radio-group>
        <el-button type="primary" @click="refresh" :loading="loading">刷新</el-button>
      </div>
    </el-card>

    <el-card class="main-card">
      <el-table
        :data="filteredData"
        style="width: 100%"
        v-loading="loading"
        stripe
        table-layout="auto"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="50" />
        <el-table-column prop="symbol" label="代码" width="120" sortable />
        <el-table-column prop="name" label="名称" width="140" sortable />
        <el-table-column prop="risk_level" label="风险等级" width="100" sortable>
          <template #default="{ row }">
            <el-tag :type="riskTag(row.risk_level)" size="small">{{ riskLabel(row.risk_level) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="entry_reason" label="入池理由" min-width="240" show-overflow-tooltip />
        <el-table-column prop="catalyst_factors" label="催化因素" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <div v-if="normalizeCatalysts(row.catalyst_factors).length" class="tag-list">
              <el-tag
                v-for="tag in normalizeCatalysts(row.catalyst_factors)"
                :key="tag"
                size="small"
                effect="plain"
                class="catalyst-tag"
              >
                {{ tag }}
              </el-tag>
            </div>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="watch_price_zone" label="观察价格区间" width="140" sortable>
          <template #default="{ row }">
            <span v-if="row.watch_price_zone" class="price-zone">{{ row.watch_price_zone }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="entry_date" label="入池日期" width="130" sortable>
          <template #default="{ row }">{{ formatDate(row.entry_date) }}</template>
        </el-table-column>
        <el-table-column prop="workflow_run_id" label="来源 Run" width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <router-link v-if="row.workflow_run_id" :to="`/workflow/${row.workflow_run_id}`" class="run-link">
              {{ row.workflow_run_id.slice(0, 8) }}...
            </router-link>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="showDetail(row)">详情</el-button>
            <el-button size="small" text type="warning" @click="openEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && filteredData.length === 0" description="观察池为空，执行一次低估发现扫描吧" />

      <div class="table-footer" v-if="total > 0">
        <div>
          <el-button
            v-if="selectedRows.length > 0"
            type="danger"
            size="small"
            @click="handleBatchDelete"
            :loading="deleting"
          >
            删除选中 ({{ selectedRows.length }})
          </el-button>
        </div>
        <span>共 {{ total }} 条记录，当前显示 {{ filteredData.length }} 条</span>
      </div>
    </el-card>

    <el-dialog v-model="detailVisible" title="观察池详情" width="720px">
      <div v-if="selectedRow" class="detail-content">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="代码">{{ selectedRow.symbol }}</el-descriptions-item>
          <el-descriptions-item label="名称">{{ selectedRow.name }}</el-descriptions-item>
          <el-descriptions-item label="风险等级">
            <el-tag :type="riskTag(selectedRow.risk_level)" size="small">{{ riskLabel(selectedRow.risk_level) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="价格区间">{{ selectedRow.watch_price_zone || '-' }}</el-descriptions-item>
          <el-descriptions-item label="上市板块">{{ selectedRow.board || '-' }}</el-descriptions-item>
          <el-descriptions-item label="股息率(%)">{{ selectedRow.dividend_yield || '-' }}</el-descriptions-item>
          <el-descriptions-item label="PE TTM">{{ selectedRow.pe_ttm || '-' }}</el-descriptions-item>
          <el-descriptions-item label="PB">{{ selectedRow.pb || '-' }}</el-descriptions-item>
          <el-descriptions-item label="最新价">{{ selectedRow.latest_price || '-' }}</el-descriptions-item>
          <el-descriptions-item label="近20交易日涨跌幅(%)">{{ selectedRow.month_return || '-' }}</el-descriptions-item>
          <el-descriptions-item label="ST标记">{{ selectedRow.st_flag || '-' }}</el-descriptions-item>
          <el-descriptions-item label="入池日期">{{ formatDate(selectedRow.entry_date) }}</el-descriptions-item>
          <el-descriptions-item label="入池理由" :span="2">{{ selectedRow.entry_reason || '-' }}</el-descriptions-item>
          <el-descriptions-item label="催化因素" :span="2">
            <div v-if="normalizeCatalysts(selectedRow.catalyst_factors).length" class="tag-list">
              <el-tag
                v-for="tag in normalizeCatalysts(selectedRow.catalyst_factors)"
                :key="tag"
                size="small"
                effect="plain"
                class="catalyst-tag"
              >
                {{ tag }}
              </el-tag>
            </div>
            <span v-else class="muted">—</span>
          </el-descriptions-item>
          <el-descriptions-item label="Run ID" :span="2"><code>{{ selectedRow.workflow_run_id }}</code></el-descriptions-item>
          <el-descriptions-item label="创建时间" :span="2">{{ formatTime(selectedRow.created_at) }}</el-descriptions-item>
        </el-descriptions>
      </div>
    </el-dialog>

    <el-dialog v-model="editVisible" title="补充缺失字段" width="620px">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="这里只允许补充自动源不稳定的字段：上市板块、股息率。其余字段由系统自动拉取、计算和生成。"
        class="edit-alert"
      />
      <el-form label-width="150px">
        <el-form-item label="上市板块">
          <el-input v-model="editForm.board" placeholder="如：主板 / 创业板 / 科创板" />
        </el-form-item>
        <el-form-item label="股息率(%)">
          <el-input v-model="editForm.dividend_yield" placeholder="如：0.6754" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { getWatchlist, updateWatchlistEntry, batchDeleteWatchlist } from '../api';
import { ElMessage, ElMessageBox } from 'element-plus';

const loading = ref(false);
const deleting = ref(false);
const saving = ref(false);
const allData = ref([]);
const searchText = ref('');
const riskFilter = ref('');
const watchlistView = ref('latest');
const detailVisible = ref(false);
const editVisible = ref(false);
const selectedRow = ref(null);
const selectedRows = ref([]);
const editForm = ref({
  id: '',
  board: '',
  dividend_yield: '',
});

const total = computed(() => allData.value.length);

const filteredData = computed(() => {
  let rows = allData.value;
  if (searchText.value) {
    const q = searchText.value.toLowerCase();
    rows = rows.filter(r => (r.symbol || '').toLowerCase().includes(q) || (r.name || '').toLowerCase().includes(q));
  }
  if (riskFilter.value) {
    rows = rows.filter(r => r.risk_level === riskFilter.value);
  }
  return rows;
});

function riskTag(r) {
  const map = { low: 'success', medium: 'warning', high: 'danger' };
  return map[r] || 'info';
}

function riskLabel(r) {
  const map = { low: '低风险', medium: '中风险', high: '高风险', unknown: '待评估' };
  return map[r] || r || '-';
}

function formatDate(t) {
  if (!t) return '-';
  try { return new Date(t).toLocaleDateString('zh-CN'); } catch { return t; }
}

function formatTime(t) {
  if (!t) return '-';
  try { return new Date(t).toLocaleString('zh-CN'); } catch { return t; }
}

function showDetail(row) {
  selectedRow.value = row;
  detailVisible.value = true;
}

function normalizeCatalysts(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value.filter(Boolean).map(v => String(v).trim()).filter(Boolean);
  if (typeof value === 'string') return value.split(/[、,，/]/).map(v => v.trim()).filter(Boolean);
  return [];
}

function handleSelectionChange(rows) {
  selectedRows.value = rows;
}

function openEdit(row) {
  editForm.value = {
    id: row.id,
    board: row.board || '',
    dividend_yield: row.dividend_yield || '',
  };
  editVisible.value = true;
}

async function submitEdit() {
  saving.value = true;
  try {
    const payload = {
      board: editForm.value.board,
      dividend_yield: editForm.value.dividend_yield,
    };
    await updateWatchlistEntry(editForm.value.id, payload);
    ElMessage.success('保存成功');
    editVisible.value = false;
    await refresh();
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || '保存失败';
    ElMessage.error(`保存失败: ${msg}`);
  } finally {
    saving.value = false;
  }
}

async function handleBatchDelete() {
  if (selectedRows.value.length === 0) return;
  try {
    await ElMessageBox.confirm(`确定删除选中的 ${selectedRows.value.length} 条记录？`, '批量删除', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    });
  } catch {
    return;
  }
  deleting.value = true;
  try {
    const ids = selectedRows.value.map(r => r.id);
    const res = await batchDeleteWatchlist(ids);
    ElMessage.success(`已删除 ${res.data?.deleted || ids.length} 条记录`);
    selectedRows.value = [];
    await refresh();
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || '删除失败';
    ElMessage.error(`删除失败: ${msg}`);
  } finally {
    deleting.value = false;
  }
}

async function refresh() {
  loading.value = true;
  try {
    const res = await getWatchlist(watchlistView.value);
    allData.value = res.data?.data || [];
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || '加载失败';
    ElMessage.error(`加载观察池失败: ${msg}`);
  } finally {
    loading.value = false;
  }
}

watch(watchlistView, () => {
  refresh();
});

onMounted(refresh);
</script>

<style scoped>
.watchlist-page { padding: 20px; max-width: 1400px; margin: 0 auto; min-height: calc(100vh - 60px); background: #0b0e14; color: #d1d4dc; }
.hero-card, .filter-card, .main-card { background: #131722; border: 1px solid #2b3139; border-radius: 12px; margin-bottom: 16px; }
:deep(.hero-card .el-card__body), :deep(.filter-card .el-card__body), :deep(.main-card .el-card__body) { background: #131722; color: #d1d4dc; }
:deep(.hero-card .el-card__header), :deep(.filter-card .el-card__header), :deep(.main-card .el-card__header) { background: #131722; border-bottom: 1px solid #2b3139; color: #d1d4dc; }
.hero-top { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.hero-title { font-size: 22px; font-weight: 700; color: #fff; }
.hero-sub { margin-top: 4px; color: #8a919e; font-size: 13px; }
.hero-actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.filter-bar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
:deep(.el-table) { background: #1a1e29 !important; --el-table-tr-bg-color: #1a1e29; --el-table-header-bg-color: #1a1e29; --el-table-border-color: #2b3139; --el-table-row-hover-bg-color: #222836; --el-table-text-color: #eef2f7; --el-table-header-text-color: #aeb6c2; }
:deep(.el-table th.el-table__cell), :deep(.el-table td.el-table__cell) { background: #1a1e29 !important; color: #eef2f7 !important; }
:deep(.el-tag--success) { background: #1a2a20; border-color: #0ECB8144; color: #0ECB81; }
:deep(.el-tag--warning) { background: #2a2418; border-color: #f59e0b44; color: #f59e0b; }
:deep(.el-tag--danger) { background: #2a1a1e; border-color: #F6465D44; color: #F6465D; }
:deep(.el-tag--info) { background: #1a1e29; border-color: #2b3139; color: #aeb6c2; }
.price-zone { font-family: monospace; color: #0ECB81; }
.run-link { color: #0ECB81; text-decoration: none; font-family: monospace; font-size: 12px; }
.run-link:hover { text-decoration: underline; }
.muted { color: #8a919e; }
.tag-list { display: flex; gap: 6px; flex-wrap: wrap; }
.catalyst-tag { margin: 0; }
.table-footer { margin-top: 12px; font-size: 12px; color: #8a919e; display: flex; justify-content: space-between; align-items: center; }
:deep(.el-dialog) { background: #131722; border: 1px solid #2b3139; }
:deep(.el-dialog__header) { background: #131722; color: #eef2f7; border-bottom: 1px solid #2b3139; }
:deep(.el-dialog__title) { color: #eef2f7; }
:deep(.el-dialog__headerbtn .el-dialog__close) { color: #8a919e; }
:deep(.el-dialog__headerbtn:hover .el-dialog__close) { color: #eef2f7; }
:deep(.el-dialog__body) { background: #131722; color: #d1d4dc; }
:deep(.el-dialog__footer) { background: #131722; border-top: 1px solid #2b3139; }
.detail-content code { color: #0ECB81; font-size: 12px; }
.edit-alert { margin-bottom: 16px; }
:deep(.el-descriptions),
:deep(.el-descriptions__body),
:deep(.el-descriptions__table) { background: #1a1e29 !important; color: #eef2f7; }
:deep(.el-descriptions__cell) { background: #1a1e29 !important; }
:deep(.el-descriptions__label) { background: #131722 !important; color: #8a919e !important; }
:deep(.el-descriptions__content) { background: #1a1e29 !important; color: #eef2f7 !important; }
:deep(.el-descriptions__body .el-descriptions__table.is-bordered .el-descriptions__cell) { border-color: #2b3139 !important; }
:deep(.el-descriptions__body .el-descriptions__table .el-descriptions__label.is-bordered-label) { background: #131722 !important; }
:deep(.el-descriptions__body .el-descriptions__table .el-descriptions__content.is-bordered-content) { background: #1a1e29 !important; }
:deep(.el-empty) { background: #1a1e29; }
:deep(.el-empty__description) { color: #8a919e; }
:deep(.el-input__wrapper), :deep(.el-textarea__inner), :deep(.el-select__wrapper) { background: #1a1e29; box-shadow: inset 0 0 0 1px #2b3139; color: #eef2f7; }
:deep(.el-input__inner), :deep(.el-textarea__inner) { color: #eef2f7; }
</style>
