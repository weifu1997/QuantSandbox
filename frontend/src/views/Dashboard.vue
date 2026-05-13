<template>
  <div class="dashboard">
    <el-card class="box-card">
      <template #header>
        <div class="controls">
          <div class="date-picker-group">
            <span class="label">模拟区间:</span>
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              format="YYYY-MM-DD"
              value-format="YYYYMMDD"
              :clearable="false"
              :shortcuts="dateShortcuts"
            />
          </div>
          <div class="button-group">
            <div class="status-light" :class="statusState">
              <span class="dot"></span>
              <span class="status-text">{{ statusText }}</span>
            </div>
            <div class="summary-state" v-if="summaryState">{{ summaryState }}</div>
            <el-button type="primary" :loading="loading" @click="fetchData">执行回测</el-button>
          </div>
        </div>
      </template>

      <div v-if="summaryTask.taskId" class="summary-task-card">
        <div class="summary-task-title">回测汇总任务状态</div>
        <div class="summary-task-grid">
          <div class="summary-task-item"><span class="k">任务ID</span><span class="v">{{ summaryTask.taskId.slice(0, 8) }}</span></div>
          <div class="summary-task-item"><span class="k">状态</span><span class="v"><span :class="['task-status-badge', summaryTask.status || 'unknown']">{{ summaryTask.status || '—' }}</span></span></div>
          <div class="summary-task-item"><span class="k">阶段</span><span class="v">{{ summaryTask.progressStage || '—' }}</span></div>
          <div class="summary-task-item"><span class="k">当前 ticker</span><span class="v">{{ summaryTask.currentTicker || '—' }}</span></div>
          <div class="summary-task-item"><span class="k">进度</span><span class="v">{{ summaryTask.totalTickers ? `${summaryTask.completedTickers}/${summaryTask.totalTickers}` : '—' }}</span></div>
          <div class="summary-task-item"><span class="k">结果来源</span><span class="v">{{ summaryTask.source ? (summaryTask.source === 'cache' ? '缓存' : '实时') : '—' }}</span></div>
          <div class="summary-task-item"><span class="k">缓存年龄</span><span class="v">{{ summaryTask.cacheAgeMs ? `${summaryTask.cacheAgeMs}ms` : '—' }}</span></div>
          <div class="summary-task-item"><span class="k">总耗时</span><span class="v">{{ summaryTask.elapsedMs ? `${summaryTask.elapsedMs}ms` : '—' }}</span></div>
          <div class="summary-task-item"><span class="k">缓存清理</span><span class="v">{{ summaryTask.cacheCleanup.remaining >= 0 ? `删 ${summaryTask.cacheCleanup.removed} / 留 ${summaryTask.cacheCleanup.remaining}` : '—' }}</span></div>
        </div>
      </div>


      <el-table :data="tableData" style="width: 100%" v-loading="loading" @row-click="goToDetail" stripe table-layout="auto">
        <el-table-column prop="ticker" label="股票代码" min-width="120" />
        <el-table-column prop="display_name" label="股票名称" min-width="140" />
        <el-table-column prop="strategy" label="量化策略" min-width="160" />
        <el-table-column prop="final_equity" label="期末净值" min-width="120">
          <template #default="scope">
            <span style="font-weight: bold">{{ scope.row.final_equity }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="return_rate" label="收益率" min-width="100">
          <template #default="scope">
            <span :style="{ color: scope.row.return_rate >= 0 ? '#f56c6c' : '#67c23a' }">
              {{ scope.row.return_rate }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="trade_count" label="交易次数" min-width="100" />
        <el-table-column label="今日交易" min-width="160">
          <template #default="scope">
            <span v-if="!scope.row.today_trades?.length" class="muted">—</span>
            <span v-else>
              <span
                v-for="(t, idx) in scope.row.today_trades"
                :key="idx"
                :class="['trade-tag', t.action === '买入' ? 'buy' : 'sell']"
              >
                {{ t.action === '买入' ? '🟢' : '🔴' }}{{ t.action }} {{ t.price }}
              </span>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="120">
          <template #default>
            <el-button size="small">详情下钻</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <div class="tip">💡 提示：默认区间截至最近交易日，点击行可进入该股票的详细 K 线回测页面</div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { getMeta, pingMeta, submitSummaryTask, getSummaryTask } from '../api';
import { ElMessage } from 'element-plus';
import dayjs from 'dayjs';

const router = useRouter();
const dateRange = ref(['20240101', dayjs().format('YYYYMMDD')]);
const latestTradeDate = ref(dayjs().format('YYYYMMDD'));
const loading = ref(false);
const tableData = ref([]);
const statusState = ref('gray');
const statusText = ref('未知');
const summaryState = ref('');
const summaryTask = ref({ taskId: '', status: '', source: '', elapsedMs: 0, cacheAgeMs: 0, progressStage: '', currentTicker: '', completedTickers: 0, totalTickers: 0, cacheCleanup: { removed: -1, remaining: -1 } });
let summaryPollTimer = null;
const dateShortcuts = [
  {
    text: '近 1 个月',
    value: () => [dayjs(latestTradeDate.value).subtract(1, 'month').toDate(), dayjs(latestTradeDate.value).toDate()],
  },
  {
    text: '近 3 个月',
    value: () => [dayjs(latestTradeDate.value).subtract(3, 'month').toDate(), dayjs(latestTradeDate.value).toDate()],
  },
  {
    text: '近 6 个月',
    value: () => [dayjs(latestTradeDate.value).subtract(6, 'month').toDate(), dayjs(latestTradeDate.value).toDate()],
  },
  {
    text: '近 1 年',
    value: () => [dayjs(latestTradeDate.value).subtract(1, 'year').toDate(), dayjs(latestTradeDate.value).toDate()],
  },
  {
    text: '今年以来',
    value: () => [dayjs(latestTradeDate.value).startOf('year').toDate(), dayjs(latestTradeDate.value).toDate()],
  },
];

const refreshStatus = async () => {
  try {
    await pingMeta();
    statusState.value = 'green';
    statusText.value = '后端在线';
  } catch (error) {
    const message = error?.message || '';
    if (message.includes('timeout')) {
      statusState.value = 'yellow';
      statusText.value = '后端慢';
    } else {
      statusState.value = 'red';
      statusText.value = '后端不可达';
    }
  }
};

const resolveStockName = (row) => String(row?.display_name || row?.name || row?.stock_name || row?.stockName || row?.ticker || '').trim();

const applySummaryPayload = (payload) => {
  const rows = Array.isArray(payload.data) ? payload.data.map((row) => ({
    ...row,
    display_name: resolveStockName(row),
  })) : [];
  const source = payload.data_source || payload.source || '';
  const note = payload.fetch_note || '';
  tableData.value = rows;
  summaryTask.value.source = payload.source || '';
  summaryTask.value.elapsedMs = Number(payload.elapsed_ms || 0);
  summaryTask.value.cacheAgeMs = Number(payload.cache_age_ms || 0);
  summaryTask.value.cacheCleanup = payload.cache_cleanup || summaryTask.value.cacheCleanup;
  if (source === 'cache_first' || source === 'cache_partial' || source === 'cache') {
    summaryState.value = `${note || '数据已返回'}（缓存）`;
  } else if (source === 'partial_fetch') {
    summaryState.value = note || '短区间优先 / 数据补齐中';
  } else {
    summaryState.value = note || '数据已返回';
  }
  if (!rows.length) {
    ElMessage.warning('当前时间区间内数据不足或无交易记录');
  }
};

const pollSummaryTask = async (taskId) => {
  try {
    const res = await getSummaryTask(taskId);
    const data = res?.data?.data || {};
    summaryTask.value.taskId = data.task_id || taskId;
    summaryTask.value.status = data.task_status || '';
    const progress = data.progress || {};
    summaryTask.value.progressStage = progress.stage || '';
    summaryTask.value.currentTicker = progress.ticker || '';
    summaryTask.value.completedTickers = Number(progress.completed_tickers || 0);
    summaryTask.value.totalTickers = Number(progress.total_tickers || progress.total || 0);
    if (progress.message) summaryState.value = progress.message;
    if (data.task_status === 'completed' && data.result) {
      applySummaryPayload(data.result);
      loading.value = false;
      if (summaryPollTimer) { clearInterval(summaryPollTimer); summaryPollTimer = null; }
    } else if (data.task_status === 'failed') {
      loading.value = false;
      if (summaryPollTimer) { clearInterval(summaryPollTimer); summaryPollTimer = null; }
      summaryState.value = data.error || '回测汇总任务失败';
      ElMessage.error(data.error || '回测汇总任务失败');
    }
  } catch (error) {
    loading.value = false;
    if (summaryPollTimer) { clearInterval(summaryPollTimer); summaryPollTimer = null; }
    ElMessage.error(error?.apiMessage || '汇总任务轮询失败');
  }
};

const fetchData = async () => {
  loading.value = true;
  summaryState.value = '正在提交汇总任务';
  summaryTask.value = { taskId: '', status: '', source: '', elapsedMs: 0, cacheAgeMs: 0, progressStage: '', currentTicker: '', completedTickers: 0, totalTickers: 0, cacheCleanup: { removed: -1, remaining: -1 } };
  if (summaryPollTimer) { clearInterval(summaryPollTimer); summaryPollTimer = null; }
  try {
    const res = await submitSummaryTask(dateRange.value[0], dateRange.value[1]);
    const data = res?.data?.data || {};
    summaryTask.value.taskId = data.task_id || '';
    summaryTask.value.status = data.cache_hit ? 'completed' : 'pending';
    summaryTask.value.cacheCleanup = data.cache_cleanup || { removed: -1, remaining: -1 }; 
    if (!summaryTask.value.taskId) throw new Error('未返回 task_id');
    await pollSummaryTask(summaryTask.value.taskId);
    if (loading.value) {
      summaryPollTimer = setInterval(() => pollSummaryTask(summaryTask.value.taskId), 1500);
    }
  } catch (error) {
    const status = error?.response?.status;
    const message = error?.message || '';
    if (status) {
      ElMessage.error(`后端接口请求失败（HTTP ${status}）`);
    } else if (message.includes('timeout')) {
      ElMessage.error('汇总任务提交超时，请稍后重试');
    } else if (message.includes('Network Error')) {
      ElMessage.error('前端无法连接后端，请检查地址、代理或浏览器网络');
    } else {
      ElMessage.error(error?.apiMessage || '获取后端数据失败，请检查接口日志');
    }
    console.error(error);
    loading.value = false;
  }
};

const goToDetail = (row) => {
  router.push({
    path: `/stock/${row.ticker}`,
    query: { start: dateRange.value[0], end: dateRange.value[1] }
  });
};

onMounted(async () => {
  try {
    const metaRes = await getMeta();
    const payload = metaRes?.data || {};
    const endDate = payload.latest_trade_date || dayjs().format('YYYYMMDD');
    latestTradeDate.value = endDate;
    dateRange.value = ['20240101', endDate];
  } catch (error) {
    console.error('getMeta failed, fallback to default range:', error);
    latestTradeDate.value = dayjs().format('YYYYMMDD');
    dateRange.value = ['20240101', latestTradeDate.value];
  } finally {
    await refreshStatus();
    await fetchData();
  }
});
</script>

<style scoped>
.dashboard { padding: 20px; max-width: 1400px; margin: 0 auto; background: #0b0e14; min-height: calc(100vh - 60px); }
:deep(.box-card) { background: #131722; border: 1px solid #2b3139; color: #d1d4dc; }
:deep(.box-card .el-card__header), :deep(.box-card .el-card__body) { background: #131722; color: #d1d4dc; }
:deep(.box-card .el-card__header) { border-bottom: 1px solid #2b3139; }
.controls { display: flex; justify-content: space-between; align-items: center; }
.date-picker-group { display: flex; align-items: center; gap: 10px; }
.label { font-size: 14px; font-weight: bold; color: #606266; }
.button-group { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.summary-state { font-size: 12px; color: #909399; }
.summary-task-card { background: #1a1e29; border: 1px solid #2b3139; border-radius: 12px; padding: 12px 14px; margin-bottom: 16px; }
.summary-task-title { font-size: 13px; font-weight: 700; color: #eef2f7; margin-bottom: 10px; }
.summary-task-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px 12px; }
.summary-task-item { background: #131722; border: 1px solid #2b3139; border-radius: 8px; padding: 8px 10px; display: flex; flex-direction: column; gap: 4px; }
.summary-task-item .k { font-size: 11px; color: #8a919e; }
.summary-task-item .v { font-size: 13px; color: #eef2f7; word-break: break-all; }
.task-status-badge { display: inline-flex; align-items: center; padding: 2px 8px; border-radius: 999px; font-size: 12px; font-weight: 700; border: 1px solid transparent; }
.task-status-badge.pending { color: #f59e0b; background: rgba(245, 158, 11, 0.12); border-color: rgba(245, 158, 11, 0.35); }
.task-status-badge.running { color: #60a5fa; background: rgba(96, 165, 250, 0.12); border-color: rgba(96, 165, 250, 0.35); }
.task-status-badge.completed { color: #0ECB81; background: rgba(14, 203, 129, 0.12); border-color: rgba(14, 203, 129, 0.35); }
.task-status-badge.failed { color: #F6465D; background: rgba(246, 70, 93, 0.12); border-color: rgba(246, 70, 93, 0.35); }
.task-status-badge.unknown { color: #8a919e; background: rgba(138, 145, 158, 0.12); border-color: rgba(138, 145, 158, 0.35); }
.status-light { display: inline-flex; align-items: center; gap: 6px; padding: 6px 10px; border-radius: 999px; border: 1px solid #dcdfe6; font-size: 12px; color: #606266; background: #fff; }
.status-light .dot { width: 8px; height: 8px; border-radius: 50%; background: #8a919e; }
.status-light.green .dot { background: #0ECB81; }
.status-light.yellow .dot { background: #f59e0b; }
.status-light.red .dot { background: #F6465D; }
.tip { margin-top: 15px; font-size: 13px; color: #909399; text-align: center; }
:deep(.el-table) { background: #1a1e29 !important; --el-table-tr-bg-color: #1a1e29; --el-table-header-bg-color: #1a1e29; --el-table-border-color: #2b3139; --el-table-row-hover-bg-color: #222836; --el-table-text-color: #eef2f7; --el-table-header-text-color: #aeb6c2; }
:deep(.el-table th.el-table__cell), :deep(.el-table td.el-table__cell) { background: #1a1e29 !important; color: #eef2f7 !important; }
:deep(.el-table .cell) { color: #eef2f7 !important; }
:deep(.el-table .el-table__header-wrapper), :deep(.el-table .el-table__body-wrapper), :deep(.el-table .el-table__fixed), :deep(.el-table .el-table__fixed-right), :deep(.el-table__inner-wrapper), :deep(.el-table__inner-wrapper::before), :deep(.el-scrollbar), :deep(.el-scrollbar__wrap), :deep(.el-scrollbar__view) { background: #1a1e29 !important; }
:deep(.el-table .el-table__body .el-table__row td), :deep(.el-table .el-table__body .el-table__row > td) { background: #1a1e29 !important; color: #eef2f7 !important; }
:deep(.el-table .el-table__body .el-table__row:hover > td) { background: #222836 !important; }
:deep(.el-table__empty-block), :deep(.el-table__empty-text) { background: #1a1e29 !important; color: #8a919e !important; }
:deep(.el-table__row) { cursor: pointer; }
.trade-tag { display: inline-block; margin-right: 6px; font-size: 12px; font-weight: 600; white-space: nowrap; }
.trade-tag.buy { color: #0ECB81; }
.trade-tag.sell { color: #F6465D; }
.muted { color: #8a919e; }
:deep(.el-table .cell) { white-space: nowrap; }
:deep(.el-table__header th .cell) { white-space: nowrap; }


</style>