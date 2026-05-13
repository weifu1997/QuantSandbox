<template>
  <div class="config-page">
    <el-card class="config-card">
      <template #header>
        <div class="header-row">
          <div>
            <div class="title">配置管理</div>
            <div class="sub">策略与因子由后端动态驱动，股票池从这里编辑，保存后写回后端 config.yaml</div>
          </div>
          <el-button @click="loadAll" :loading="loading">刷新</el-button>
        </div>
      </template>

      <el-form label-width="120px" class="config-form">
        <!-- ===== 账户参数 ===== -->
        <el-form-item label="初始资金">
          <div class="param-grid single-row">
            <div class="param-item">
              <div class="param-label">initial_cash</div>
              <div class="param-desc">回测初始资金，影响下单整手约束和资金利用率</div>
              <el-input-number v-model="accountForm.initial_cash" :min="1" :step="1000" controls-position="right" style="width: 100%" />
            </div>
            <div class="param-item">
              <div class="param-label">commission_rate</div>
              <div class="param-desc">佣金费率</div>
              <el-input-number v-model="accountForm.commission_rate" :min="0" :step="0.0001" :precision="6" controls-position="right" style="width: 100%" />
            </div>
            <div class="param-item">
              <div class="param-label">tax_rate</div>
              <div class="param-desc">印花税费率</div>
              <el-input-number v-model="accountForm.tax_rate" :min="0" :step="0.0001" :precision="6" controls-position="right" style="width: 100%" />
            </div>
          </div>
        </el-form-item>

        <!-- ===== 股票池 ===== -->
        <el-form-item label="股票池">
          <div class="stock-pool-editor">
            <div class="stock-pool-hint">支持批量编辑：每行一个股票代码，适合大股票池；保存时会自动去重并校验格式。</div>
            <el-input
              v-model="stockPoolText"
              type="textarea"
              :autosize="{ minRows: 10, maxRows: 24 }"
              placeholder="例如：&#10;sh601318&#10;sz000858&#10;bjxxxxxx"
              @paste="handleStockPoolPaste"
            />
            <div class="stock-pool-actions">
              <el-button size="small" plain @click="formatStockPoolText">格式化</el-button>
              <el-button size="small" plain @click="exportStockPoolText">导出</el-button>
            </div>
            <div class="stock-pool-meta">当前输入 {{ stockPoolTextLines }} 行，去重后预期 {{ stockPoolPreviewCount }} 只</div>
          </div>
        </el-form-item>

        <!-- ===== 策略选择 (动态) ===== -->
        <el-form-item label="策略选择">
          <el-select v-model="strategyName" placeholder="选择策略" style="width: 320px" @change="onStrategyChange" :loading="loadingStrategies">
            <el-option v-for="s in strategyList" :key="s.name" :label="strategyOptionLabel(s)" :value="s.name" />
          </el-select>
          <div class="strategy-hint" v-if="currentStrategyDesc">{{ currentStrategyDesc }}</div>
          <div class="strategy-hint muted" v-if="!strategyList.length && !loadingStrategies">后端未返回策略列表，请检查服务状态</div>
        </el-form-item>

        <!-- ===== 策略参数 (动态) ===== -->
        <el-form-item label="策略参数" v-if="currentStrategy">
          <div class="param-grid">
            <template v-for="(schema, key) in currentStrategy.parameter_schema || {}" :key="key">
              <div class="param-item">
                <div class="param-label">{{ key }}</div>
                <div class="param-desc">{{ schema.description || schema.type || '' }}</div>
                <el-input-number
                  v-if="schema.type === 'integer' || schema.type === 'number'"
                  v-model="strategyParams[key]"
                  :min="schema.minimum ?? undefined"
                  :max="schema.maximum ?? undefined"
                  :step="schema.type === 'integer' ? 1 : 0.1"
                  controls-position="right"
                  style="width: 100%"
                />
                <el-input
                  v-else
                  v-model="strategyParams[key]"
                  :placeholder="String(schema.default ?? '')"
                  style="width: 100%"
                />
              </div>
            </template>
            <div v-if="!Object.keys(currentStrategy.parameter_schema || {}).length" class="param-empty">
              该策略无可配置参数
            </div>
          </div>
        </el-form-item>

        <!-- ===== 因子列表 (动态) ===== -->
        <el-form-item label="可用因子">
          <div class="factor-grid" v-if="factorList.length">
            <el-tag
              v-for="f in factorList"
              :key="f.name"
              :type="factorCategoryType(f.category)"
              effect="dark"
              size="small"
              class="factor-tag"
            >
              {{ f.name }}
              <el-tooltip v-if="f.description" :content="f.description" placement="top">
                <span style="margin-left:4px;cursor:help">ⓘ</span>
              </el-tooltip>
            </el-tag>
          </div>
          <div class="strategy-hint muted" v-else-if="!loadingFactors">暂无因子数据</div>
        </el-form-item>

        <!-- ===== 当前配置预览 ===== -->
        <el-form-item label="当前配置预览">
          <div class="preview-summary">
            <div class="preview-summary-line">股票池：{{ stockPoolPreviewCount }} 只｜策略：{{ strategyLabel }}</div>
            <div class="preview-summary-line">初始资金：{{ accountForm.initial_cash }} ｜ 佣金：{{ accountForm.commission_rate }} ｜ 印花税：{{ accountForm.tax_rate }}</div>
            <div class="preview-summary-line muted">参数项：{{ Object.keys(strategyParams).length }} 个｜当前输入：{{ stockPoolTextLines }} 行</div>
          </div>
          <el-collapse class="preview-collapse">
            <el-collapse-item title="查看完整配置 JSON" name="preview-json">
              <pre class="preview-box">{{ previewText }}</pre>
            </el-collapse-item>
          </el-collapse>
        </el-form-item>

        <!-- ===== 当前策略 ===== -->
        <el-form-item label="当前策略" v-if="currentStrategy">
          <el-tag class="strategy-badge" effect="dark" size="large" :type="strategyBadgeType">
            本次回测将使用：{{ strategyLabel }}
          </el-tag>
        </el-form-item>

        <!-- ===== 操作按钮 ===== -->
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="saveConfig">保存配置</el-button>
          <el-button @click="$router.push('/')">返回首页</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getConfig, updateConfig, getStrategies, getFactors } from '../api'

const loading = ref(false)
const saving = ref(false)
const loadingStrategies = ref(false)
const loadingFactors = ref(false)
const stockPool = ref([])
const stockPoolText = ref('')
const strategyName = ref('target_weight_demo')
const strategyParams = ref({})
const accountForm = ref({ initial_cash: 15000, commission_rate: 0.00025, tax_rate: 0.0005 })

// ===== 动态数据 =====
const strategyList = ref([])
const factorList = ref([])

// ===== 计算属性 =====
const currentStrategy = computed(() => strategyList.value.find(s => s.name === strategyName.value) || null)
const currentStrategyDesc = computed(() => currentStrategy.value?.description || '')
const strategyLabel = computed(() => {
  if (!currentStrategy.value) return strategyName.value
  return `${currentStrategy.value.name} ${currentStrategy.value.description ? '— ' + currentStrategy.value.description.slice(0, 30) + '…' : ''}`
})
const strategyBadgeType = computed(() => {
  const idx = strategyList.value.findIndex(s => s.name === strategyName.value)
  const types = ['success', 'warning', 'danger', 'info']
  return types[idx % types.length] || 'success'
})

const normalizeStock = (s) => (s || '').trim()
const stockPoolFromText = computed(() => stockPoolText.value.split(/\r?\n/).map(normalizeStock).filter(Boolean))
const stockPoolTextLines = computed(() => stockPoolText.value ? stockPoolText.value.split(/\r?\n/).length : 0)
const stockPoolPreviewCount = computed(() => [...new Set(stockPoolFromText.value)].length)
const previewText = computed(() => JSON.stringify({
  account: accountForm.value,
  stock_pool: stockPoolFromText.value,
  strategy: {
    name: strategyName.value,
    parameters: strategyParams.value,
  },
}, null, 2))

// ===== 工具函数 =====
const strategyOptionLabel = (s) => `${s.name} — ${(s.description || '').slice(0, 40)}`

const factorCategoryType = (cat) => {
  if (cat === 'technical') return ''
  if (cat === 'fundamental') return 'success'
  if (cat === 'sentiment') return 'warning'
  return 'info'
}

const buildDefaultParams = (schema) => {
  const defaults = {}
  if (schema && typeof schema === 'object') {
    for (const [key, def] of Object.entries(schema)) {
      if (def && typeof def === 'object' && 'default' in def) {
        defaults[key] = def.default
      }
    }
  }
  return defaults
}

// ===== 数据加载 =====
const loadAll = async () => {
  loading.value = true
  await Promise.all([loadConfig(), loadStrategies(), loadFactors()])
  loading.value = false
}

const loadConfig = async () => {
  try {
    const res = await getConfig()
    stockPool.value = Array.isArray(res.data.stock_pool) ? [...res.data.stock_pool] : []
    stockPoolText.value = stockPool.value.join('\n')
    accountForm.value = {
      initial_cash: Number(res.data.account?.initial_cash ?? 15000),
      commission_rate: Number(res.data.account?.commission_rate ?? 0.00025),
      tax_rate: Number(res.data.account?.tax_rate ?? 0.0005),
    }
    const cfgName = res.data.strategy?.name
    if (cfgName && strategyList.value.some(s => s.name === cfgName)) {
      strategyName.value = cfgName
    }
    const cfgParams = res.data.strategy?.parameters || {}
    strategyParams.value = { ...buildDefaultParams(currentStrategy.value?.parameter_schema), ...cfgParams }
  } catch (e) {
    ElMessage.error('读取配置失败')
    console.error(e)
  }
}

const loadStrategies = async () => {
  loadingStrategies.value = true
  try {
    const res = await getStrategies()
    const list = res?.data?.strategies || []
    strategyList.value = list
    if (list.length && !list.find(s => s.name === strategyName.value)) {
      strategyName.value = list[0].name
      strategyParams.value = buildDefaultParams(list[0].parameter_schema)
    }
  } catch (e) {
    console.error('Failed to load strategies', e)
  } finally {
    loadingStrategies.value = false
  }
}

const loadFactors = async () => {
  loadingFactors.value = true
  try {
    const res = await getFactors()
    factorList.value = res?.data?.factors || []
  } catch (e) {
    console.error('Failed to load factors', e)
  } finally {
    loadingFactors.value = false
  }
}

// ===== 策略切换 =====
const onStrategyChange = () => {
  if (currentStrategy.value) {
    strategyParams.value = { ...buildDefaultParams(currentStrategy.value.parameter_schema) }
  }
}

// ===== 股票池操作 =====
const stockCodePattern = /^(sh|sz|bj)\d{6}$/

const formatStockPoolText = () => {
  const cleaned = stockPoolText.value
    .split(/\r?\n/)
    .map(normalizeStock)
    .filter(Boolean)
    .map(code => code.toLowerCase())
  stockPoolText.value = [...new Set(cleaned)].join('\n')
  ElMessage.success('已格式化股票池')
}

const exportStockPoolText = async () => {
  const text = stockPoolFromText.value.join('\n')
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制整理后的股票池')
  } catch (e) {
    console.error(e)
    ElMessage.error('复制失败')
  }
}

const handleStockPoolPaste = () => {
  window.setTimeout(() => {
    formatStockPoolText()
  }, 0)
}

// ===== 保存 =====
const saveConfig = async () => {
  const normalizedPool = stockPoolFromText.value
  const uniquePool = [...new Set(normalizedPool)]
  if (uniquePool.length !== normalizedPool.length) {
    ElMessage.error('股票池里有重复代码，请去重后再保存')
    return
  }
  if (uniquePool.some(code => !stockCodePattern.test(code))) {
    ElMessage.error('股票代码格式不对，需符合 sh600036 / sz000858 / bjxxxxxx')
    return
  }

  const params = { ...strategyParams.value }
  saving.value = true
  try {
    await updateConfig({
      stock_pool: uniquePool,
      strategy_name: strategyName.value,
      strategy_parameters: params,
      initial_cash: Number(accountForm.value.initial_cash),
      commission_rate: Number(accountForm.value.commission_rate),
      tax_rate: Number(accountForm.value.tax_rate),
    })
    ElMessage.success('配置已保存。建议立即重跑 summary/detail，验证新资金与费率已生效')
  } catch (e) {
    ElMessage.error('保存配置失败')
    console.error(e)
  } finally {
    saving.value = false
  }
}

// ===== 初始化 =====
onMounted(async () => {
  loading.value = true
  await loadStrategies()
  await loadFactors()
  await loadConfig()
  loading.value = false
})
</script>

<style scoped>
.config-page { padding: 20px; max-width: 1200px; margin: 0 auto; background: #0b0e14; min-height: calc(100vh - 60px); color: #d1d4dc; }
.config-card { background: #131722; border: 1px solid #2B3139; border-radius: 10px; }
.header-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.title { font-size: 20px; font-weight: 600; color: #eef2f7; }
.sub { margin-top: 4px; color: #8a919e; font-size: 13px; }
.strategy-hint { margin-top: 8px; color: #d1d4dc; font-size: 12px; }
.muted { color: #8a919e !important; }

.preview-summary { display: flex; flex-direction: column; gap: 4px; margin-bottom: 8px; }
.preview-summary-line { color: #eef2f7; font-size: 13px; }
.preview-collapse { width: 100%; }

.stock-pool-editor { display: flex; flex-direction: column; gap: 10px; width: 100%; }
.stock-pool-hint { color: #8a919e; font-size: 12px; }
.stock-pool-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.stock-pool-meta { color: #8a919e; font-size: 12px; }

.param-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; width: 100%; }
.param-grid.single-row { grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
.param-item { background: #1a1e29; border: 1px solid #2B3139; border-radius: 8px; padding: 12px; }
.param-label { margin-bottom: 4px; color: #d1d4dc; font-size: 13px; font-weight: 600; font-family: monospace; }
.param-desc { margin-bottom: 8px; color: #8a919e; font-size: 11px; }
.param-empty { color: #8a919e; font-size: 13px; padding: 8px; }

.factor-grid { display: flex; flex-wrap: wrap; gap: 6px; }
.factor-tag { cursor: default; }

.preview-box { width: 100%; margin: 0; padding: 12px; background: #0f131a; color: #eef2f7; border: 1px solid #2B3139; border-radius: 8px; overflow: auto; }
.strategy-badge { font-size: 14px; letter-spacing: 0.3px; }

:deep(.el-card__body) { background: #131722; }
:deep(.el-card__header) { background: #131722; border-bottom: 1px solid #2B3139; }
:deep(.el-form-item__label) { color: #aeb6c2 !important; }
:deep(.el-input__wrapper) { background: #0f131a !important; box-shadow: 0 0 0 1px #3b4351 inset !important; }
:deep(.el-input__inner) { color: #eef2f7 !important; }
:deep(.el-textarea__inner) { background: #0f131a !important; color: #eef2f7 !important; box-shadow: 0 0 0 1px #3b4351 inset !important; }
:deep(.el-collapse) { border: none; }
:deep(.el-collapse-item__header) { color: #aeb6c2; background: #1a1e29; border: 1px solid #2B3139; border-radius: 6px; padding: 8px 12px; margin-bottom: 4px; }
:deep(.el-collapse-item__wrap) { background: transparent; border: none; }
:deep(.el-collapse-item__content) { padding: 8px 0; }
</style>
