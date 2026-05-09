<template>
  <div class="workflow-page">
    <!-- Hero -->
    <el-card class="hero-card">
      <div class="hero-top">
        <div>
          <div class="hero-title">🔍 低估发现流</div>
          <div class="hero-sub">全自动选股 → 数据验证 → 资讯研判 → 观察池输出</div>
        </div>
        <div class="hero-actions">
          <el-tag v-if="activeRun" :type="statusTagType" size="large">
            {{ statusLabel }}
          </el-tag>
          <el-button @click="$router.push('/workflow/history')">查看历史</el-button>
          <el-button @click="$router.push('/')">返回首页</el-button>
        </div>
      </div>
    </el-card>

    <!-- Trigger Panel -->
    <el-card class="trigger-card">
      <template #header>
        <span class="card-title">⚡ 启动新扫描</span>
      </template>
      <div class="trigger-form">
        <div class="form-row">
          <div class="form-item">
            <label>选股模板</label>
            <el-radio-group v-model="useDefaultTemplate" :disabled="running">
              <el-radio-button :value="true">默认模板（全A低估值）</el-radio-button>
              <el-radio-button :value="false">自定义查询</el-radio-button>
            </el-radio-group>
          </div>
          <div class="form-item">
            <label>批量大小</label>
            <el-input-number v-model="batchSize" :min="1" :max="20" :disabled="running" />
          </div>
        </div>
        <div class="form-row" v-if="!useDefaultTemplate">
          <div class="form-item full-width">
            <label>自定义妙想选股查询</label>
            <el-input
              v-model="customQuery"
              type="textarea"
              :rows="2"
              placeholder="输入妙想选股查询语句..."
              :disabled="running"
            />
          </div>
        </div>
        <div class="form-row">
          <el-button
            type="success"
            size="large"
            :loading="running"
            :disabled="running"
            @click="startRun"
          >
            {{ running ? '扫描中...' : '🚀 启动扫描' }}
          </el-button>
        </div>
        <div v-if="showQuery" class="resolved-query">
          💡 实际查询：{{ activeResolvedQuery }}
        </div>
      </div>
    </el-card>

    <!-- Progress Panel -->
    <el-card class="progress-card" v-if="activeRun">
      <template #header>
        <span class="card-title">📊 执行进度</span>
      </template>

      <div class="run-meta">
        <span class="meta-item">Run ID: <code>{{ activeRunId }}</code></span>
        <span class="meta-item">状态: <el-tag :type="statusTagType" size="small">{{ statusLabel }}</el-tag></span>
        <span class="meta-item">步骤: {{ completedSteps }} / {{ totalSteps }}</span>
      </div>

      <!-- Step progress -->
      <div class="steps-timeline">
        <div
          v-for="step in steps"
          :key="step.step_code"
          class="step-node"
          :class="`step-${step.uiStatus}`"
        >
          <div class="step-dot">
            <span v-if="step.uiStatus === 'running'" class="dot-spinner"></span>
            <span v-else-if="step.uiStatus === 'done'">✅</span>
            <span v-else-if="step.uiStatus === 'failed'">❌</span>
            <span v-else>⏳</span>
          </div>
          <div class="step-info">
            <div class="step-name">{{ step.step_name }}</div>
            <div class="step-code">{{ step.step_code }}</div>
            <div class="step-duration" v-if="step.uiDuration">
              {{ step.uiDuration }}
            </div>
            <div class="step-error" v-if="step.error_message">
              {{ step.error_message }}
            </div>
          </div>
          <el-button
            v-if="step.uiStatus === 'done' && step.result_data"
            size="small"
            text
            type="primary"
            @click="showStepDetail(step)"
          >
            查看结果
          </el-button>
        </div>
      </div>

      <!-- Quick result summary -->
      <div v-if="activeRunStatus === 'completed'" class="result-summary">
        <div class="summary-stats">
          <div class="stat">
            <div class="stat-value">{{ candidates.length }}</div>
            <div class="stat-label">候选股</div>
          </div>
          <div class="stat">
            <div class="stat-value">{{ watchlist.length }}</div>
            <div class="stat-label">入池观察</div>
          </div>
        </div>
        <div class="summary-actions">
          <el-button type="primary" @click="goToDetail">查看完整报告 →</el-button>
          <el-button @click="goToWatchlist">查看观察池 →</el-button>
        </div>
      </div>
    </el-card>

    <!-- Step Detail Dialog -->
    <el-dialog
      v-model="stepDialogVisible"
      :title="selectedStep?.step_name"
      width="700px"
      :close-on-click-modal="false"
    >
      <div v-if="selectedStep" class="step-detail-content">
        <pre class="result-json">{{ JSON.stringify(selectedStep.result_data, null, 2) }}</pre>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { runLowValueWorkflow, getWorkflowRun } from '../api';

const router = useRouter();

// Form
const useDefaultTemplate = ref(true);
const customQuery = ref('');
const batchSize = ref(5);
const running = ref(false);
const showQuery = ref(false);

// Run state
const activeRunId = ref('');
const activeRun = ref(null);
const activeRunStatus = ref('');
const activeResolvedQuery = ref('');
const steps = ref([]);
const candidates = ref([]);
const watchlist = ref([]);

// Step detail dialog
const stepDialogVisible = ref(false);
const selectedStep = ref(null);

// Polling
let pollTimer = null;

const STEP_LIST = [
  { code: 'xuangu', name: 'Step 1 智能选股' },
  { code: 'risk', name: 'Step 1.5 快速排雷' },
  { code: 'data', name: 'Step 2 数据结构化' },
  { code: 'search', name: 'Step 3 资讯研判' },
  { code: 'zixuan', name: 'Step 4 自选同步' },
];

const totalSteps = computed(() => activeRun.value?.total_steps || 5);
const completedSteps = computed(() => steps.value.filter(s => s.uiStatus === 'done').length);

const statusTagType = computed(() => {
  const map = {
    running: 'warning',
    completed: 'success',
    failed: 'danger',
  };
  return map[activeRunStatus.value] || 'info';
});

const statusLabel = computed(() => {
  const map = {
    running: '运行中',
    completed: '已完成',
    failed: '失败',
  };
  return map[activeRunStatus.value] || activeRunStatus.value || '未启动';
});

function buildStepUI(runStatus, serverSteps) {
  const stepMap = {};
  (serverSteps || []).forEach(s => { stepMap[s.step_code] = s; });

  return STEP_LIST.map(({ code, name }) => {
    const server = stepMap[code];
    if (!server) {
      return { step_code: code, step_name: name, uiStatus: 'pending', result_data: null, error_message: null };
    }
    let uiStatus = 'pending';
    const srvStatus = server.status;
    if (srvStatus === 'completed') uiStatus = 'done';
    else if (srvStatus === 'failed') uiStatus = 'failed';
    else if (srvStatus === 'running') uiStatus = 'running';
    else if (runStatus === 'completed' && srvStatus !== 'completed') uiStatus = 'failed';

    let uiDuration = '';
    if (server.started_at && server.completed_at) {
      const s = new Date(server.started_at);
      const e = new Date(server.completed_at);
      const sec = Math.round((e - s) / 1000);
      uiDuration = sec >= 60 ? `${Math.floor(sec/60)}m${sec%60}s` : `${sec}s`;
    }

    return {
      step_code: code,
      step_name: name,
      uiStatus,
      result_data: server.result_data,
      error_message: server.error_message,
      uiDuration,
    };
  });
}

async function startRun() {
  running.value = true;
  showQuery.value = true;
  try {
    const payload = {
      use_default_template: useDefaultTemplate.value,
      batch_size: batchSize.value,
    };
    if (!useDefaultTemplate.value && customQuery.value.trim()) {
      payload.custom_query = customQuery.value.trim();
    }
    const res = await runLowValueWorkflow(payload);
    activeRunId.value = res.data.run_id;
    ElMessage.success(`扫描已启动，Run ID: ${activeRunId.value}`);
    startPolling();
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || '启动失败';
    ElMessage.error(`启动失败: ${msg}`);
    running.value = false;
  }
}

function startPolling() {
  stopPolling();
  pollTimer = setInterval(fetchRunStatus, 2000);
  fetchRunStatus(); // immediate first poll
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function fetchRunStatus() {
  if (!activeRunId.value) return;
  try {
    const res = await getWorkflowRun(activeRunId.value);
    const data = res.data?.data || {};
    activeRun.value = data.run || {};
    activeRunStatus.value = activeRun.value.status || '';
    activeResolvedQuery.value = activeRun.value.config?.resolved_query || '';
    steps.value = buildStepUI(activeRunStatus.value, data.steps || []);
    candidates.value = data.candidates || [];
    watchlist.value = data.watchlist || [];

    if (activeRunStatus.value === 'completed' || activeRunStatus.value === 'failed') {
      stopPolling();
      running.value = false;
      if (activeRunStatus.value === 'completed') {
        ElMessage.success('扫描完成！');
      } else {
        ElMessage.error('扫描失败，请查看步骤详情');
      }
    }
  } catch (e) {
    console.error('Poll error:', e);
  }
}

function showStepDetail(step) {
  selectedStep.value = step;
  stepDialogVisible.value = true;
}

function goToDetail() {
  if (activeRunId.value) {
    router.push(`/workflow/${activeRunId.value}`);
  }
}

function goToWatchlist() {
  router.push('/watchlist');
}
onUnmounted(() => {
  stopPolling();
});
</script>

<style scoped>
.workflow-page { padding: 20px; max-width: 1400px; margin: 0 auto; min-height: calc(100vh - 60px); background: #0b0e14; color: #d1d4dc; }

.hero-card, .trigger-card, .progress-card {
  background: #131722; border: 1px solid #2b3139; border-radius: 12px; margin-bottom: 16px;
}
:deep(.hero-card .el-card__body), :deep(.trigger-card .el-card__body), :deep(.progress-card .el-card__body) {
  background: #131722; color: #d1d4dc;
}
:deep(.hero-card .el-card__header), :deep(.trigger-card .el-card__header), :deep(.progress-card .el-card__header) {
  background: #131722; border-bottom: 1px solid #2b3139; color: #d1d4dc;
}

.hero-top { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.hero-title { font-size: 22px; font-weight: 700; color: #fff; }
.hero-sub { margin-top: 4px; color: #8a919e; font-size: 13px; }
.hero-actions { display: flex; gap: 10px; align-items: center; }

.card-title { font-size: 16px; font-weight: 600; color: #eef2f7; }

.trigger-form { display: flex; flex-direction: column; gap: 16px; }
.form-row { display: flex; gap: 24px; align-items: flex-start; flex-wrap: wrap; }
.form-item { display: flex; flex-direction: column; gap: 6px; }
.form-item label { font-size: 13px; color: #8a919e; }
.full-width { flex: 1; min-width: 300px; }

.resolved-query { font-size: 13px; color: #8a919e; padding: 8px 12px; background: #1a1e29; border-radius: 6px; }

.run-meta { display: flex; gap: 24px; flex-wrap: wrap; margin-bottom: 20px; font-size: 13px; color: #aeb6c2; }
.run-meta code { color: #0ECB81; font-size: 12px; }

.steps-timeline { display: flex; flex-direction: column; gap: 8px; }
.step-node {
  display: flex; align-items: center; gap: 12px; padding: 10px 14px;
  background: #1a1e29; border-radius: 8px; transition: background .2s;
}
.step-node.step-running { background: #1e2d24; border: 1px solid #0ECB8155; }
.step-node.step-done { background: #1a2a20; }
.step-node.step-failed { background: #2a1a1e; border: 1px solid #F6465D55; }

.step-dot { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; font-size: 14px; }
.dot-spinner {
  width: 16px; height: 16px; border: 2px solid #2b3139; border-top-color: #0ECB81;
  border-radius: 50%; display: inline-block; animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.step-info { flex: 1; }
.step-name { font-size: 14px; font-weight: 500; color: #eef2f7; }
.step-code { font-size: 11px; color: #8a919e; }
.step-duration { font-size: 11px; color: #aeb6c2; margin-top: 2px; }
.step-error { font-size: 12px; color: #F6465D; margin-top: 4px; }

.result-summary { margin-top: 20px; padding: 16px; background: #1a2a20; border-radius: 8px; border: 1px solid #0ECB8133; }
.summary-stats { display: flex; gap: 32px; margin-bottom: 12px; }
.stat { text-align: center; }
.stat-value { font-size: 28px; font-weight: 700; color: #0ECB81; }
.stat-label { font-size: 12px; color: #aeb6c2; }
.summary-actions { display: flex; gap: 10px; }

.step-detail-content .result-json {
  background: #0b0e14; color: #d1d4dc; padding: 16px; border-radius: 8px;
  font-size: 12px; max-height: 500px; overflow: auto; margin: 0;
}

:deep(.el-dialog) { background: #131722; border: 1px solid #2b3139; }
:deep(.el-dialog__header) { background: #131722; color: #eef2f7; border-bottom: 1px solid #2b3139; }
:deep(.el-dialog__body) { background: #131722; color: #d1d4dc; }

:deep(.el-empty) { background: #1a1e29; }
:deep(.el-empty__description) { color: #8a919e; }

/* Tag dark mode */
:deep(.el-tag--success) { background: #1a2a20; border-color: #0ECB8144; color: #0ECB81; }
:deep(.el-tag--warning) { background: #2a2418; border-color: #f59e0b44; color: #f59e0b; }
:deep(.el-tag--danger) { background: #2a1a1e; border-color: #F6465D44; color: #F6465D; }
:deep(.el-tag--info) { background: #1a1e29; border-color: #2b3139; color: #aeb6c2; }

:deep(.el-radio-button__inner) { background: #1a1e29; border-color: #2b3139; color: #aeb6c2; }
:deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) { background: #0ECB81; border-color: #0ECB81; color: #fff; }
:deep(.el-input-number .el-input__wrapper) { background: #1a1e29; box-shadow: inset 0 0 0 1px #2b3139; }
:deep(.el-input__inner) { color: #eef2f7; }
</style>
