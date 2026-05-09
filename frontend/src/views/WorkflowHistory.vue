<template>
  <div class="history-page">
    <el-card class="hero-card">
      <div class="hero-top">
        <div>
          <div class="hero-title">🕘 工作流历史</div>
          <div class="hero-sub">查看最近运行记录并快速跳转详情页</div>
        </div>
        <div class="hero-actions">
          <el-button @click="$router.push('/workflow')">🚀 启动新扫描</el-button>
          <el-button @click="refresh" :loading="loading">刷新</el-button>
        </div>
      </div>
    </el-card>

    <el-card class="filter-card">
      <div class="filter-bar">
        <el-select v-model="statusFilter" clearable placeholder="按状态筛选" style="width: 180px">
          <el-option label="运行中" value="running" />
          <el-option label="已完成" value="completed" />
          <el-option label="失败" value="failed" />
        </el-select>
        <el-input v-model="userFilter" clearable placeholder="按用户筛选" style="width: 220px" />
        <el-input-number v-model="limit" :min="1" :max="100" />
      </div>
    </el-card>

    <el-card class="main-card">
      <el-table :data="rows" v-loading="loading" stripe table-layout="auto">
        <el-table-column prop="id" label="Run ID" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <router-link :to="`/workflow/${row.id}`" class="run-link">{{ row.id }}</router-link>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="user_id" label="用户" width="140" show-overflow-tooltip />
        <el-table-column prop="total_steps" label="步骤数" width="90" />
        <el-table-column prop="started_at" label="开始时间" width="180">
          <template #default="{ row }">{{ formatTime(row.started_at) }}</template>
        </el-table-column>
        <el-table-column prop="completed_at" label="结束时间" width="180">
          <template #default="{ row }">{{ formatTime(row.completed_at) }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="$router.push(`/workflow/${row.id}`)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && rows.length === 0" description="暂无运行记录" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue';
import { ElMessage } from 'element-plus';
import { listWorkflowRuns } from '../api';

const loading = ref(false);
const rows = ref([]);
const statusFilter = ref('');
const userFilter = ref('');
const limit = ref(20);

function statusTag(status) {
  if (status === 'completed') return 'success';
  if (status === 'running') return 'warning';
  if (status === 'failed') return 'danger';
  return 'info';
}

function statusLabel(status) {
  return { completed: '已完成', running: '运行中', failed: '失败' }[status] || status || '-';
}

function formatTime(value) {
  if (!value) return '-';
  try { return new Date(value).toLocaleString('zh-CN'); } catch { return value; }
}

async function refresh() {
  loading.value = true;
  try {
    const params = { limit: limit.value };
    if (statusFilter.value) params.status = statusFilter.value;
    if (userFilter.value) params.user_id = userFilter.value;
    const res = await listWorkflowRuns(params);
    rows.value = res.data?.data || [];
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || '加载失败';
    ElMessage.error(`加载历史失败: ${msg}`);
  } finally {
    loading.value = false;
  }
}

watch([statusFilter, userFilter, limit], refresh);
onMounted(refresh);
</script>

<style scoped>
.history-page { padding: 20px; max-width: 1400px; margin: 0 auto; min-height: calc(100vh - 60px); background: #0b0e14; color: #d1d4dc; }
.hero-card, .filter-card, .main-card { background: #131722; border: 1px solid #2b3139; border-radius: 12px; margin-bottom: 16px; }
:deep(.hero-card .el-card__body), :deep(.filter-card .el-card__body), :deep(.main-card .el-card__body) { background: #131722; color: #d1d4dc; }
.hero-top { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.hero-title { font-size: 22px; font-weight: 700; color: #fff; }
.hero-sub { margin-top: 4px; color: #8a919e; font-size: 13px; }
.hero-actions, .filter-bar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.run-link { color: #4ea1ff; text-decoration: none; }
.run-link:hover { text-decoration: underline; }
</style>
