<template>
  <div class="mx-page">
    <el-card class="mx-card">
      <template #header>
        <div class="header-row">
          <div>
            <div class="title">妙想金融数据</div>
            <div class="sub">调用后端 mx-data 适配器，查询东方财富权威数据</div>
          </div>
          <el-button @click="$router.push('/')">返回首页</el-button>
        </div>
      </template>

      <el-form label-width="120px">
        <el-form-item label="查询内容">
          <el-input v-model="query" placeholder="正常交易 非ST 非停牌 排除科创板 排除创业板 排除北交所..." />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="runQuery">查询</el-button>
        </el-form-item>
      </el-form>

      <el-divider />

      <el-row :gutter="12">
        <el-col :span="12">
          <el-card shadow="never" class="panel">
            <template #header>返回摘要</template>
            <pre>{{ stdout || '暂无结果' }}</pre>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="never" class="panel">
            <template #header>原始 JSON</template>
            <pre>{{ jsonText || '暂无结果' }}</pre>
          </el-card>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import api from '../api';

const query = ref('正常交易 非ST 非停牌 排除科创板 排除创业板 排除北交所 股价3元到35元 市净率PB大于0.5 小于1.5 市盈率TTM大于5 小于20 股息率大于3% 最近60日涨幅大于-8% 小于10% 日均成交额大于5000万 股价站在250 日均线（年线）上方 近 60 日振幅：≤30% 无大额质押、无证监会立案调查、无业绩预亏预警');
const loading = ref(false);
const stdout = ref('');
const jsonText = ref('');

const runQuery = async () => {
  const q = query.value.trim();
  if (!q) {
    ElMessage.warning('请输入查询内容');
    return;
  }
  loading.value = true;
  try {
    const res = await api.post('/mx/data', { query: q });
    stdout.value = res.data.stdout || '';
    jsonText.value = res.data.raw_json ? JSON.stringify(res.data.raw_json, null, 2) : '';
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
.mx-page { padding: 20px; max-width: 1400px; margin: 0 auto; background: #0b0e14; min-height: calc(100vh - 60px); color: #d1d4dc; }
.mx-card { background: #131722; border: 1px solid #2B3139; border-radius: 10px; }
.header-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.title { font-size: 20px; font-weight: 600; color: #eef2f7; }
.sub { margin-top: 4px; color: #8a919e; font-size: 13px; }
.panel { background: #1a1e29; border: 1px solid #2B3139; color: #d1d4dc; }
pre { white-space: pre-wrap; word-break: break-word; margin: 0; min-height: 240px; background: #0f131a; color: #eef2f7; border: 1px solid #2b3139; border-radius: 8px; padding: 12px; }
:deep(.el-card__body) { background: #131722; }
:deep(.el-card__header) { background: #131722; border-bottom: 1px solid #2B3139; }
:deep(.el-input__wrapper) { background: #0f131a !important; box-shadow: 0 0 0 1px #3b4351 inset !important; }
:deep(.el-input__inner) { color: #eef2f7 !important; }
</style>
