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
          <MxSearchTab :initial-query="searchQuery" />
        </el-tab-pane>
        <el-tab-pane label="妙想金融数据" name="data">
          <MxDataTab :initial-query="dataQuery" />
        </el-tab-pane>
        <el-tab-pane label="妙想智能选股" name="xuangu">
          <MxXuanguTab :initial-query="xuanguQuery" />
        </el-tab-pane>
        <el-tab-pane label="妙想模拟组合" name="moni">
          <MxMoniTab />
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';
import MxSearchTab from './mx/MxSearchTab.vue';
import MxDataTab from './mx/MxDataTab.vue';
import MxXuanguTab from './mx/MxXuanguTab.vue';
import MxMoniTab from './mx/MxMoniTab.vue';

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
</script>

<style scoped>
.mx-page { padding: 20px; max-width: 1600px; margin: 0 auto; background: #0b0e14; min-height: calc(100vh - 60px); color: #d1d4dc; }
.hero-card,
.main-card { background: #131722; border: 1px solid #2b3139; border-radius: 12px; }
.hero-card { margin-bottom: 16px; }
.hero-top { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.hero-title { font-size: 22px; font-weight: 700; color: #fff; }
.hero-sub { margin-top: 4px; color: #8a919e; font-size: 13px; }
.main-card { padding: 0; }
.mx-tabs :deep(.el-tabs--border-card) { background: #131722; border-color: #2b3139; box-shadow: none; }
.mx-tabs :deep(.el-tabs--border-card > .el-tabs__header) { background: #131722; border-color: #2b3139; margin: 0; }
.mx-tabs :deep(.el-tabs__nav-wrap) { background: #131722; }
.mx-tabs :deep(.el-tabs__nav-scroll) { background: #131722; }
.mx-tabs :deep(.el-tabs__nav) { background: #131722; }
.mx-tabs :deep(.el-tabs--border-card > .el-tabs__header .el-tabs__item) { color: #aeb6c2; border-color: #2b3139; background: #131722; }
.mx-tabs :deep(.el-tabs--border-card > .el-tabs__header .el-tabs__item:hover) { color: #eef2f7; }
.mx-tabs :deep(.el-tabs--border-card > .el-tabs__header .el-tabs__item.is-active) { color: #eef2f7; background: #1a1e29; border-bottom-color: #1a1e29; }
.mx-tabs :deep(.el-tabs__content) { padding: 16px; background: #131722; }
.mx-tabs :deep(.el-tab-pane) { background: #131722; }
.mx-tabs :deep(.el-tabs__nav-wrap::after) { background: #2b3139; }
</style>
