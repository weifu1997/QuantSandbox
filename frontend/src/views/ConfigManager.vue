<template>
  <div class="config-page">
    <el-card class="config-card">
      <template #header>
        <div class="header-row">
          <div>
            <div class="title">配置管理</div>
            <div class="sub">股票池和策略都从这里改，保存后写回后端 config.yaml</div>
          </div>
          <el-button @click="loadConfig" :loading="loading">刷新</el-button>
        </div>
      </template>

      <el-form label-width="120px" class="config-form">
        <el-form-item label="股票池">
          <div class="stock-pool-editor">
            <div class="stock-pool-hint">支持批量编辑：每行一个股票代码，适合大股票池；保存时会自动去重并校验格式。</div>
            <el-input
              v-model="stockPoolText"
              type="textarea"
              :autosize="{ minRows: 10, maxRows: 24 }"
              placeholder="例如：\nsh601318\nsz000858\nbjxxxxxx"
              @paste="handleStockPoolPaste"
            />
            <div class="stock-pool-actions">
              <el-button size="small" plain @click="formatStockPoolText">格式化</el-button>
              <el-button size="small" plain @click="exportStockPoolText">导出</el-button>
            </div>
            <div class="stock-pool-meta">当前输入 {{ stockPoolTextLines }} 行，去重后预期 {{ stockPoolPreviewCount }} 只</div>
          </div>
        </el-form-item>

        <el-form-item label="策略选择">
          <el-select v-model="strategyName" placeholder="选择策略" style="width: 320px" @change="syncStrategyDefaults">
            <el-option label="dual_ma 双均线" value="dual_ma" />
            <el-option label="bollinger_bands 布林带" value="bollinger_bands" />
            <el-option label="rsi_reversal RSI 反转" value="rsi_reversal" />
          </el-select>
          <div class="strategy-hint">当前回测策略将直接使用这里选择的策略与参数。</div>
        </el-form-item>

        <el-form-item label="当前配置预览">
          <div class="preview-summary">
            <div class="preview-summary-line">股票池：{{ stockPoolPreviewCount }} 只｜策略：{{ strategyLabel }}</div>
            <div class="preview-summary-line muted">参数项：{{ currentStrategyFields.length }} 个｜当前输入：{{ stockPoolTextLines }} 行</div>
          </div>
          <el-collapse class="preview-collapse">
            <el-collapse-item title="查看完整配置 JSON" name="preview-json">
              <pre class="preview-box">{{ previewText }}</pre>
            </el-collapse-item>
          </el-collapse>
        </el-form-item>

        <el-form-item label="当前策略">
          <el-tag class="strategy-badge" effect="dark" size="large" :type="strategyBadgeType">
            本次回测将使用：{{ strategyLabel }}
          </el-tag>
        </el-form-item>

        <el-form-item label="策略参数">
          <div class="param-grid">
            <template v-for="field in currentStrategyFields" :key="field.key">
              <div class="param-item">
                <div class="param-label">{{ field.label }}</div>
                <div class="param-desc">{{ field.desc }}</div>
                <el-input-number
                  v-if="field.type === 'number'"
                  v-model="strategyParams[field.key]"
                  :min="field.min ?? 0"
                  :step="field.step ?? 1"
                  controls-position="right"
                  style="width: 100%"
                />
              </div>
            </template>
          </div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="saveConfig">保存配置</el-button>
          <el-button @click="$router.push('/')">返回首页</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { getConfig, updateConfig } from '../api';

const loading = ref(false);
const saving = ref(false);
const stockPool = ref([]);
const stockPoolText = ref('');
const strategyName = ref('dual_ma');
const strategyParams = ref({ fast_period: 5, slow_period: 20 });

const strategyMeta = {
  dual_ma: {
    label: 'dual_ma 双均线',
    fields: [
      { key: 'fast_period', label: '快线周期', desc: '短期均线窗口', type: 'number', min: 1, step: 1 },
      { key: 'slow_period', label: '慢线周期', desc: '长期均线窗口', type: 'number', min: 2, step: 1 },
    ],
    defaults: { fast_period: 5, slow_period: 20 },
  },
  bollinger_bands: {
    label: 'bollinger_bands 布林带',
    fields: [
      { key: 'window', label: '窗口周期', desc: '均值与标准差窗口', type: 'number', min: 1, step: 1 },
      { key: 'std_dev', label: '标准差倍数', desc: '通道宽度倍数', type: 'number', min: 0.1, step: 0.1 },
    ],
    defaults: { window: 20, std_dev: 2.0 },
  },
  rsi_reversal: {
    label: 'rsi_reversal RSI 反转',
    fields: [
      { key: 'window', label: 'RSI 窗口', desc: 'RSI 计算周期', type: 'number', min: 1, step: 1 },
      { key: 'buy_threshold', label: '买入阈值', desc: '低于此值视为超卖', type: 'number', min: 1, step: 1 },
      { key: 'sell_threshold', label: '卖出阈值', desc: '高于此值视为超买', type: 'number', min: 1, step: 1 },
    ],
    defaults: { window: 14, buy_threshold: 30, sell_threshold: 70 },
  },
};

const currentStrategy = computed(() => strategyMeta[strategyName.value] || strategyMeta.dual_ma);
const currentStrategyFields = computed(() => currentStrategy.value.fields);
const strategyLabel = computed(() => currentStrategy.value.label);
const strategyBadgeType = computed(() => {
  if (strategyName.value === 'bollinger_bands') return 'warning';
  if (strategyName.value === 'rsi_reversal') return 'danger';
  return 'success';
});
const normalizeStock = (s) => (s || '').trim();
const stockPoolFromText = computed(() => stockPoolText.value.split(/\r?\n/).map(normalizeStock).filter(Boolean));
const stockPoolTextLines = computed(() => stockPoolText.value ? stockPoolText.value.split(/\r?\n/).length : 0);
const stockPoolPreviewCount = computed(() => [...new Set(stockPoolFromText.value)].length);
const previewText = computed(() => JSON.stringify({
  stock_pool: stockPoolFromText.value,
  strategy: {
    name: strategyName.value,
    parameters: strategyParams.value,
  },
}, null, 2));

const loadConfig = async () => {
  loading.value = true;
  try {
    const res = await getConfig();
    stockPool.value = Array.isArray(res.data.stock_pool) ? [...res.data.stock_pool] : [];
    stockPoolText.value = stockPool.value.join('\n');
    strategyName.value = strategyMeta[res.data.strategy?.name] ? res.data.strategy.name : 'dual_ma';
    strategyParams.value = { ...(strategyMeta[res.data.strategy?.name] || strategyMeta.dual_ma).defaults, ...(res.data.strategy?.parameters || {}) };
  } catch (e) {
    ElMessage.error('读取配置失败');
    console.error(e);
  } finally {
    loading.value = false;
  }
};

const syncStrategyDefaults = () => {
  strategyParams.value = { ...currentStrategy.value.defaults };
};

const stockCodePattern = /^(sh|sz|bj)\d{6}$/;

const formatStockPoolText = () => {
  const cleaned = stockPoolText.value
    .split(/\r?\n/)
    .map(normalizeStock)
    .filter(Boolean)
    .map(code => code.toLowerCase());
  stockPoolText.value = [...new Set(cleaned)].join('\n');
  ElMessage.success('已格式化股票池');
};

const exportStockPoolText = async () => {
  const text = stockPoolFromText.value.join('\n');
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success('已复制整理后的股票池');
  } catch (e) {
    console.error(e);
    ElMessage.error('复制失败');
  }
};

const handleStockPoolPaste = () => {
  window.setTimeout(() => {
    formatStockPoolText();
  }, 0);
};

const saveConfig = async () => {
  const normalizedPool = stockPoolFromText.value;
  const uniquePool = [...new Set(normalizedPool)];
  if (uniquePool.length !== normalizedPool.length) {
    ElMessage.error('股票池里有重复代码，请去重后再保存');
    return;
  }
  if (uniquePool.some(code => !stockCodePattern.test(code))) {
    ElMessage.error('股票代码格式不对，需符合 sh600036 / sz000858 / bjxxxxxx');
    return;
  }

  const params = { ...currentStrategy.value.defaults, ...strategyParams.value };
  const meta = currentStrategy.value;
  const requiredKeys = meta.fields.map(f => f.key);
  for (const key of requiredKeys) {
    if (!(key in params)) {
      ElMessage.error(`缺少策略参数: ${key}`);
      return;
    }
    if (typeof params[key] !== 'number' || Number.isNaN(params[key])) {
      ElMessage.error(`策略参数 ${key} 必须是数字`);
      return;
    }
  }

  saving.value = true;
  try {
    await updateConfig({
      stock_pool: uniquePool,
      strategy_name: strategyName.value,
      strategy_parameters: params,
    });
    ElMessage.success('配置已保存');
  } catch (e) {
    ElMessage.error('保存配置失败');
    console.error(e);
  } finally {
    saving.value = false;
  }
};

onMounted(loadConfig);
</script>

<style scoped>
.config-page { padding: 20px; max-width: 1200px; margin: 0 auto; background: #0b0e14; min-height: calc(100vh - 60px); color: #d1d4dc; }
.config-card { background: #131722; border: 1px solid #2B3139; border-radius: 10px; }
.header-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.title { font-size: 20px; font-weight: 600; color: #eef2f7; }
.sub { margin-top: 4px; color: #8a919e; font-size: 13px; }
.strategy-hint { margin-top: 8px; color: #8a919e; font-size: 12px; }
.preview-summary { display: flex; flex-direction: column; gap: 4px; margin-bottom: 8px; }
.preview-summary-line { color: #eef2f7; font-size: 13px; }
.preview-collapse { width: 100%; }
.stock-pool-editor { display: flex; flex-direction: column; gap: 10px; width: 100%; }
.stock-pool-hint { color: #8a919e; font-size: 12px; }
.stock-pool-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.stock-pool-meta { color: #8a919e; font-size: 12px; }
.param-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; width: 100%; }
.param-item { background: #1a1e29; border: 1px solid #2B3139; border-radius: 8px; padding: 12px; }
.param-label { margin-bottom: 4px; color: #d1d4dc; font-size: 13px; font-weight: 600; }
.param-desc { margin-bottom: 8px; color: #8a919e; font-size: 12px; }
.preview-box { width: 100%; margin: 0; padding: 12px; background: #0f131a; color: #eef2f7; border: 1px solid #2B3139; border-radius: 8px; overflow: auto; }
.strategy-badge { font-size: 14px; letter-spacing: 0.3px; }
:deep(.el-card__body) { background: #131722; }
:deep(.el-card__header) { background: #131722; border-bottom: 1px solid #2B3139; }
:deep(.el-input__wrapper) { background: #0f131a !important; box-shadow: 0 0 0 1px #3b4351 inset !important; }
:deep(.el-input__inner) { color: #eef2f7 !important; }
:deep(.el-textarea__inner) { background: #0f131a !important; color: #eef2f7 !important; box-shadow: 0 0 0 1px #3b4351 inset !important; }
</style>
