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
            <el-button type="success" @click="advance30Days">前进 30 天 ⏩</el-button>
            <el-button type="primary" :loading="loading" @click="fetchData">执行回测</el-button>
          </div>
        </div>
      </template>

      <el-table :data="tableData" style="width: 100%" v-loading="loading" @row-click="goToDetail" stripe table-layout="auto">
        <el-table-column prop="ticker" label="股票代码" min-width="120" />
        <el-table-column prop="name" label="股票名称" min-width="140" />
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
        <el-table-column label="操作" min-width="120">
          <template #default>
            <el-button size="small">详情下钻</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <div class="tip">💡 提示：默认区间截至今天，点击行可进入该股票的详细 K 线回测页面</div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { getMeta, getSummary, pingMeta } from '../api';
import { ElMessage } from 'element-plus';
import dayjs from 'dayjs';

const router = useRouter();
const dateRange = ref(['20240101', dayjs().format('YYYYMMDD')]); // 默认区间：截至当前日期
const loading = ref(false);
const tableData = ref([]);
const statusState = ref('gray');
const statusText = ref('未知');
const summaryState = ref('');
const dateShortcuts = [
  {
    text: '近 1 个月',
    value: () => [dayjs().subtract(1, 'month').toDate(), dayjs().toDate()],
  },
  {
    text: '近 3 个月',
    value: () => [dayjs().subtract(3, 'month').toDate(), dayjs().toDate()],
  },
  {
    text: '近 6 个月',
    value: () => [dayjs().subtract(6, 'month').toDate(), dayjs().toDate()],
  },
  {
    text: '近 1 年',
    value: () => [dayjs().subtract(1, 'year').toDate(), dayjs().toDate()],
  },
  {
    text: '今年以来',
    value: () => [dayjs().startOf('year').toDate(), dayjs().toDate()],
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

// 核心逻辑：时间轴一次前进 30 天
const advance30Days = () => {
  const currentEnd = dayjs(dateRange.value[1]);
  // 起始日期变为上次的结束日期 + 1天
  const nextStart = currentEnd.add(1, 'day');
  // 结束日期往后推 30 天
  const nextEnd = nextStart.add(30, 'day');
  
  dateRange.value = [nextStart.format('YYYYMMDD'), nextEnd.format('YYYYMMDD')];
  fetchData(); // 自动触发回测
};


const fetchData = async () => {
  loading.value = true;
  summaryState.value = '数据加载中';
  try {
    const res = await getSummary(dateRange.value[0], dateRange.value[1]);
    const payload = res?.data || {};
    const rows = Array.isArray(payload.data) ? payload.data : [];
    const source = payload.data_source || '';
    const note = payload.fetch_note || '';

    tableData.value = rows;
    if (source === 'cache_first' || source === 'cache_partial') {
      summaryState.value = note || '短区间优先 / 数据补齐中';
    } else if (source === 'partial_fetch') {
      summaryState.value = note || '短区间优先 / 数据补齐中';
    } else {
      summaryState.value = note || '数据已返回';
    }

    if (!rows.length) {
      ElMessage.warning('当前时间区间内数据不足或无交易记录');
    }
  } catch (error) {
    const status = error?.response?.status;
    const message = error?.message || '';
    if (status) {
      ElMessage.error(`后端接口请求失败（HTTP ${status}）`);
    } else if (message.includes('timeout')) {
      ElMessage.error('后端响应超时，请稍后重试');
    } else if (message.includes('Network Error')) {
      ElMessage.error('前端无法连接后端，请检查地址、代理或浏览器网络');
    } else {
      ElMessage.error('获取后端数据失败，请检查接口日志');
    }
    console.error(error);
  } finally {
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
    await getMeta();
  } catch (error) {
    console.error('getMeta failed, fallback to default range:', error);
  } finally {
    dateRange.value = ['20240101', dayjs().format('YYYYMMDD')];
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
:deep(.el-table .cell) { white-space: nowrap; }
:deep(.el-table__header th .cell) { white-space: nowrap; }
</style>