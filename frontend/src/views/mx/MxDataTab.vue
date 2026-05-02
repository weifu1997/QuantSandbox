<template>
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
      <el-button type="primary" :loading="loading" @click="runData">查询</el-button>
    </div>
  </el-card>

  <el-row :gutter="12" class="result-row">
    <el-col :span="24">
      <el-card shadow="never" class="result-card">
        <template #header>查询摘要</template>
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="状态">{{ meta.status || '暂无' }}</el-descriptions-item>
          <el-descriptions-item label="输出目录">{{ meta.output_dir || '暂无' }}</el-descriptions-item>
          <el-descriptions-item label="返回码">{{ meta.returncode ?? '暂无' }}</el-descriptions-item>
        </el-descriptions>
      </el-card>
    </el-col>
  </el-row>

  <el-row :gutter="12" class="result-row">
    <el-col :span="24">
      <el-card shadow="never" class="result-card">
        <template #header>运行输出</template>
        <pre class="data-output">{{ stdout || '暂无结果' }}</pre>
      </el-card>
    </el-col>
  </el-row>

  <el-collapse class="raw-collapse">
    <el-collapse-item title="查看原始 JSON" name="data-raw">
      <pre>{{ jsonText || '暂无结果' }}</pre>
    </el-collapse-item>
  </el-collapse>
</template>

<script setup>
import { ref, reactive, watch } from 'vue';
import { ElMessage } from 'element-plus';
import api from '../../api';

const props = defineProps({
  initialQuery: { type: String, default: '东方财富最新价' },
});

const dataQuery = ref(props.initialQuery);
watch(() => props.initialQuery, (val) => {
  if (val) dataQuery.value = val;
});

const loading = ref(false);
const stdout = ref('');
const jsonText = ref('');
const meta = reactive({ status: '', output_dir: '', returncode: null });

const runData = async () => {
  const q = dataQuery.value.trim();
  if (!q) return ElMessage.warning('请输入查询内容');
  loading.value = true;
  try {
    const res = await api.post('/mx/data', { query: q });
    stdout.value = res.data.stdout || '';
    jsonText.value = res.data.raw_json ? JSON.stringify(res.data.raw_json, null, 2) : '';
    meta.status = res.data.status || '';
    meta.output_dir = res.data.output_dir || '';
    meta.returncode = res.data.returncode ?? null;
    ElMessage.success('查询成功');
  } catch (e) {
    ElMessage.error('妙想数据查询失败');
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
.card-header-inline { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.muted { color: #8a919e; font-size: 12px; }
.query-row { display: flex; gap: 12px; align-items: center; }
.query-row :deep(.el-input) { flex: 1; }
:deep(.el-input__wrapper) { background: #0f131a !important; box-shadow: 0 0 0 1px #3b4351 inset !important; }
:deep(.el-input__inner) { color: #eef2f7 !important; }
:deep(.el-input__inner::placeholder) { color: #8a919e !important; }
:deep(.el-button--primary) { background: #0ECB81; border-color: #0ECB81; color: #08110d; font-weight: 600; }
:deep(.el-button--primary:hover), :deep(.el-button--primary:focus) { background: #19d08d; border-color: #19d08d; color: #08110d; }
pre { white-space: pre-wrap; word-break: break-word; margin: 0; min-height: 220px; color: #eef2f7; background: #0f131a; border: 1px solid #2b3139; border-radius: 8px; padding: 12px; }
.data-output { min-height: 320px; line-height: 1.65; }
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
</style>
