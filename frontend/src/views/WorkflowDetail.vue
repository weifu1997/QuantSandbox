<template>
  <div class="detail-page">
    <!-- Back + Title -->
    <div class="top-bar">
      <el-button text @click="$router.push('/workflow')">← 返回执行页</el-button>
      <el-tag v-if="run" :type="statusTag" size="large">{{ statusLabel }}</el-tag>
    </div>

    <el-card class="hero-card" v-loading="loading">
      <div class="hero-top">
        <div>
          <div class="hero-title">📋 运行详情</div>
          <div class="hero-sub">Run ID: <code>{{ runId }}</code></div>
        </div>
      </div>
    </el-card>

    <!-- Run Info Card -->
    <el-card class="info-card">
      <template #header><span class="card-title">运行概要</span></template>
      <div class="info-grid" v-if="run">
        <div class="info-item">
          <span class="info-label">状态</span>
          <el-tag :type="statusTag" size="small">{{ statusLabel }}</el-tag>
        </div>
        <div class="info-item">
          <span class="info-label">用户</span>
          <span>{{ run.user_id || '-' }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">总步骤</span>
          <span>{{ run.total_steps }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">开始时间</span>
          <span>{{ formatTime(run.started_at) }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">结束时间</span>
          <span>{{ formatTime(run.completed_at) }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">创建时间</span>
          <span>{{ formatTime(run.created_at) }}</span>
        </div>
      </div>
      <div class="config-block" v-if="run?.config">
        <div class="config-title">执行配置</div>
        <pre class="config-json">{{ JSON.stringify(run.config, null, 2) }}</pre>
      </div>
    </el-card>

    <!-- Tabs -->
    <el-card class="main-card">
      <el-tabs v-model="activeTab" type="border-card" class="detail-tabs">
        <!-- Steps Tab -->
        <el-tab-pane label="📊 执行步骤" name="steps">
          <div class="steps-grid">
            <div
              v-for="step in steps"
              :key="step.id"
              class="step-card"
              :class="`step-card-${getStepStatus(step)}`"
              @click="openStepDrawer(step)"
            >
              <div class="step-header">
                <span class="step-badge">{{ step.step_code }}</span>
                <el-tag :type="stepTagType(step)" size="small">{{ step.status }}</el-tag>
              </div>
              <div class="step-body">
                <div class="step-name">{{ step.step_name }}</div>
                <div class="step-time" v-if="step.started_at">
                  {{ formatTime(step.started_at) }} → {{ formatTime(step.completed_at) }}
                </div>
                <div class="step-error-preview" v-if="step.error_message">
                  ❌ {{ truncate(step.error_message, 80) }}
                </div>
                <div class="step-result-hint" v-if="step.result_data">
                  ✅ 有结果数据，点击查看
                </div>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <!-- Candidates Tab -->
        <el-tab-pane :label="`🎯 候选股 (${candidates.length})`" name="candidates">
          <el-table :data="candidates" style="width: 100%" v-if="candidates.length">
            <el-table-column prop="symbol" label="代码" width="120" />
            <el-table-column prop="name" label="名称" width="140" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="candidateStatusTag(row.status)" size="small">{{ candidateStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="入选理由" min-width="200">
              <template #default="{ row }">
                <span>{{ formatReason(row.reason) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="数据" min-width="200">
              <template #default="{ row }">
                <pre class="cell-pre" v-if="row.data">{{ JSON.stringify(row.data, null, 1) }}</pre>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="170">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="暂无候选股" />
        </el-tab-pane>

        <!-- Watchlist Tab -->
        <el-tab-pane :label="`👁️ 观察池 (${watchlist.length})`" name="watchlist">
          <el-table :data="watchlist" style="width: 100%" v-if="watchlist.length">
            <el-table-column prop="symbol" label="代码" width="120" />
            <el-table-column prop="name" label="名称" width="140" />
            <el-table-column prop="risk_level" label="风险等级" width="100">
              <template #default="{ row }">
                <el-tag :type="riskTag(row.risk_level)" size="small">{{ riskLabel(row.risk_level) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="entry_reason" label="入池理由" min-width="200" />
            <el-table-column prop="catalyst_factors" label="催化因素" min-width="200" />
            <el-table-column prop="watch_price_zone" label="观察价格区间" width="140" />
            <el-table-column prop="entry_date" label="入池日期" width="120">
              <template #default="{ row }">{{ formatDate(row.entry_date) }}</template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="暂无观察池记录" />
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- Step Detail Drawer -->
    <el-drawer
      v-model="drawerVisible"
      :title="drawerStep?.step_name || '步骤详情'"
      size="600px"
    >
      <div v-if="drawerStep" class="drawer-body">
        <div class="drawer-meta">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="步骤代码">{{ drawerStep.step_code }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="stepTagType(drawerStep)" size="small">{{ drawerStep.status }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="开始时间">{{ formatTime(drawerStep.started_at) }}</el-descriptions-item>
            <el-descriptions-item label="结束时间">{{ formatTime(drawerStep.completed_at) }}</el-descriptions-item>
          </el-descriptions>
        </div>
        <div class="drawer-section" v-if="drawerStep.error_message">
          <div class="drawer-section-title">❌ 错误信息</div>
          <pre class="drawer-pre error-pre">{{ drawerStep.error_message }}</pre>
        </div>
        <div class="drawer-section" v-if="drawerStep.result_data">
          <div class="drawer-section-title">📦 结果数据</div>
          <pre class="drawer-pre">{{ JSON.stringify(drawerStep.result_data, null, 2) }}</pre>
        </div>
        <el-empty v-if="!drawerStep.result_data && !drawerStep.error_message" description="暂无数据" />
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import { getWorkflowRun } from '../api';
import { ElMessage } from 'element-plus';

const route = useRoute();
const runId = computed(() => route.params.runId);

const loading = ref(false);
const run = ref(null);
const steps = ref([]);
const candidates = ref([]);
const watchlist = ref([]);
const activeTab = ref('steps');
const drawerVisible = ref(false);
const drawerStep = ref(null);

const statusTag = computed(() => {
  const s = run.value?.status;
  if (s === 'completed') return 'success';
  if (s === 'running') return 'warning';
  if (s === 'failed') return 'danger';
  return 'info';
});

const statusLabel = computed(() => {
  const map = { completed: '已完成', running: '运行中', failed: '失败' };
  return map[run.value?.status] || run.value?.status || '-';
});

function formatTime(t) {
  if (!t) return '-';
  try { return new Date(t).toLocaleString('zh-CN'); } catch { return t; }
}

function formatDate(t) {
  if (!t) return '-';
  try { return new Date(t).toLocaleDateString('zh-CN'); } catch { return t; }
}

function truncate(s, n) { return s && s.length > n ? s.slice(0, n) + '...' : s; }

function getStepStatus(step) {
  const s = step.status;
  if (s === 'completed') return 'done';
  if (s === 'running') return 'running';
  if (s === 'failed') return 'failed';
  return 'pending';
}

function stepTagType(step) {
  const s = step.status;
  if (s === 'completed') return 'success';
  if (s === 'running') return 'warning';
  if (s === 'failed') return 'danger';
  return 'info';
}

function candidateStatusTag(s) {
  const map = { selected: 'success', eliminated: 'danger', insufficient_data: 'warning', pending: 'info', accepted: 'success', rejected: 'danger' };
  return map[s] || 'info';
}

function candidateStatusLabel(s) {
  const map = { selected: '通过', eliminated: '淘汰', insufficient_data: '数据不足', pending: '待处理', accepted: '通过', rejected: '淘汰' };
  return map[s] || s;
}

function formatReason(reason) {
  if (!reason) return '-';
  if (typeof reason === 'string') return reason;
  if (typeof reason === 'object') {
    const parts = [];
    if (reason.from) parts.push(`来源: ${reason.from}`);
    if (reason.step) parts.push(`步骤: ${reason.step}`);
    if (reason.reason) parts.push(`原因: ${reason.reason}`);
    return parts.join(' | ') || JSON.stringify(reason);
  }
  return String(reason);
}

function riskTag(r) {
  const map = { low: 'success', medium: 'warning', high: 'danger', unknown: 'info' };
  return map[r] || 'info';
}

function riskLabel(r) {
  const map = { low: '低风险', medium: '中风险', high: '高风险', unknown: '待评估' };
  return map[r] || r || '-';
}

function openStepDrawer(step) {
  drawerStep.value = step;
  drawerVisible.value = true;
}

async function fetchData() {
  loading.value = true;
  try {
    const res = await getWorkflowRun(runId.value);
    const data = res.data?.data || {};
    run.value = data.run || null;
    steps.value = data.steps || [];
    candidates.value = data.candidates || [];
    watchlist.value = data.watchlist || [];
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || '加载失败';
    ElMessage.error(`加载运行详情失败: ${msg}`);
  } finally {
    loading.value = false;
  }
}

onMounted(fetchData);
</script>

<style scoped>
.detail-page { padding: 20px; max-width: 1400px; margin: 0 auto; min-height: calc(100vh - 60px); background: #0b0e14; color: #d1d4dc; }

.top-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }

.hero-card, .info-card, .main-card {
  background: #131722; border: 1px solid #2b3139; border-radius: 12px; margin-bottom: 16px;
}
:deep(.hero-card .el-card__body), :deep(.info-card .el-card__body), :deep(.main-card .el-card__body) {
  background: #131722; color: #d1d4dc;
}
:deep(.hero-card .el-card__header), :deep(.info-card .el-card__header), :deep(.main-card .el-card__header) {
  background: #131722; border-bottom: 1px solid #2b3139; color: #d1d4dc;
}

/* Tag dark mode override */
:deep(.el-tag) {
  --el-tag-bg-color: #1a1e29;
  --el-tag-border-color: #2b3139;
  --el-tag-hover-color: #222836;
  border-color: #2b3139;
}
:deep(.el-tag--success) { background: #1a2a20; border-color: #0ECB8144; color: #0ECB81; }
:deep(.el-tag--warning) { background: #2a2418; border-color: #f59e0b44; color: #f59e0b; }
:deep(.el-tag--danger) { background: #2a1a1e; border-color: #F6465D44; color: #F6465D; }
:deep(.el-tag--info) { background: #1a1e29; border-color: #2b3139; color: #aeb6c2; }

.hero-top { display: flex; justify-content: space-between; align-items: center; }
.hero-title { font-size: 20px; font-weight: 700; color: #fff; }
.hero-sub { margin-top: 4px; color: #8a919e; font-size: 13px; }
.hero-sub code { color: #0ECB81; font-size: 12px; }

.card-title { font-size: 15px; font-weight: 600; color: #eef2f7; }

.info-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
.info-item { display: flex; flex-direction: column; gap: 4px; }
.info-label { font-size: 12px; color: #8a919e; }
.info-item > span:last-child { font-size: 14px; color: #eef2f7; }

.config-block { margin-top: 16px; padding-top: 12px; border-top: 1px solid #2b3139; }
.config-title { font-size: 13px; color: #8a919e; margin-bottom: 8px; }
.config-json { background: #0b0e14; color: #aeb6c2; padding: 10px; border-radius: 6px; font-size: 12px; margin: 0; }

/* Steps Grid */
.steps-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
.step-card {
  background: #1a1e29; border: 1px solid #2b3139; border-radius: 10px; padding: 14px;
  cursor: pointer; transition: all .2s;
}
.step-card:hover { border-color: #0ECB81; transform: translateY(-1px); }
.step-card-done { border-left: 3px solid #0ECB81; }
.step-card-running { border-left: 3px solid #f59e0b; }
.step-card-failed { border-left: 3px solid #F6465D; }
.step-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.step-badge { font-size: 11px; color: #0ECB81; font-weight: 600; }
.step-body { }
.step-name { font-size: 14px; font-weight: 500; color: #eef2f7; margin-bottom: 4px; }
.step-time { font-size: 11px; color: #8a919e; }
.step-error-preview { font-size: 12px; color: #F6465D; margin-top: 6px; }
.step-result-hint { font-size: 12px; color: #0ECB81; margin-top: 6px; }

/* Tabs */
.detail-tabs :deep(.el-tabs--border-card) { background: #131722; border-color: #2b3139; box-shadow: none; }
.detail-tabs :deep(.el-tabs--border-card > .el-tabs__header) { background: #131722; border-color: #2b3139; }
.detail-tabs :deep(.el-tabs--border-card > .el-tabs__header .el-tabs__item) { color: #aeb6c2; background: #131722; border-color: #2b3139; }
.detail-tabs :deep(.el-tabs--border-card > .el-tabs__header .el-tabs__item.is-active) { color: #fff; background: #1a1e29; }
.detail-tabs :deep(.el-tabs__content) { padding: 16px; background: #1a1e29; }
.detail-tabs :deep(.el-tab-pane) { background: #1a1e29; }

/* Empty state */
:deep(.el-empty) { background: #1a1e29; --el-empty-fill-color-0: #2b3139; --el-empty-fill-color-1: #222836; --el-empty-fill-color-2: #1a1e29; --el-empty-fill-color-3: #2b3139; --el-empty-fill-color-4: #222836; --el-empty-fill-color-5: #1a1e29; --el-empty-fill-color-6: #2b3139; --el-empty-fill-color-7: #222836; --el-empty-fill-color-8: #1a1e29; --el-empty-fill-color-9: #2b3139; }
:deep(.el-empty__description) { color: #8a919e; }

/* Table override */
:deep(.el-table) { background: #1a1e29 !important; --el-table-tr-bg-color: #1a1e29; --el-table-header-bg-color: #1a1e29; --el-table-border-color: #2b3139; --el-table-row-hover-bg-color: #222836; --el-table-text-color: #eef2f7; --el-table-header-text-color: #aeb6c2; }
:deep(.el-table th.el-table__cell), :deep(.el-table td.el-table__cell) { background: #1a1e29 !important; color: #eef2f7 !important; }

.cell-pre { margin: 0; font-size: 11px; color: #aeb6c2; white-space: pre-wrap; max-height: 100px; overflow: auto; background: #0b0e14; }

/* Drawer */
:deep(.el-drawer) { background: #131722; color: #d1d4dc; }
:deep(.el-drawer__header) { color: #eef2f7; border-bottom: 1px solid #2b3139; margin-bottom: 0; }
:deep(.el-drawer__body) { padding: 16px; }

.drawer-body { }
.drawer-meta { margin-bottom: 16px; }
:deep(.el-descriptions) { background: #1a1e29; }
:deep(.el-descriptions__label) { background: #131722; color: #8a919e; }
:deep(.el-descriptions__content) { background: #1a1e29; color: #eef2f7; }

.drawer-section { margin-top: 16px; }
.drawer-section-title { font-size: 14px; font-weight: 600; color: #eef2f7; margin-bottom: 8px; }
.drawer-pre { background: #0b0e14; color: #d1d4dc; padding: 12px; border-radius: 8px; font-size: 12px; max-height: 500px; overflow: auto; margin: 0; }
.error-pre { border: 1px solid #F6465D44; }
</style>
