<template>
  <div class="alpha-research-page">
    <el-card class="page-card">
      <template #header>
        <div class="header-row">
          <div>
            <div class="title">Alpha Research</div>
            <div class="subtitle">参数化运行 /api/research/report，展示因子 IC、分组收益与 TopN 策略摘要。</div>
          </div>
          <div class="header-actions">
            <el-tag type="success" effect="dark">PR6 Frontend</el-tag>
            <el-button @click="resetForm">重置</el-button>
            <el-button type="primary" :loading="loading" @click="runReport">生成报告</el-button>
          </div>
        </div>
      </template>

      <el-form label-position="top" class="research-form">
        <div class="form-grid">
          <el-form-item label="股票池">
            <el-input
              v-model="form.tickersText"
              type="textarea"
              :autosize="{ minRows: 6, maxRows: 10 }"
              placeholder="每行一个 ticker，例如：&#10;sh600519&#10;sz000858"
            />
          </el-form-item>

          <el-form-item label="研究因子">
            <el-select
              v-model="form.factors"
              multiple
              filterable
              collapse-tags
              collapse-tags-tooltip
              placeholder="选择一个或多个因子"
            >
              <el-option
                v-for="factor in factorOptions"
                :key="factor.name"
                :label="factor.name"
                :value="factor.name"
              >
                <div class="factor-option">
                  <span>{{ factor.name }}</span>
                  <span class="factor-option-desc">{{ factor.description || factor.category || 'research factor' }}</span>
                </div>
              </el-option>
            </el-select>
          </el-form-item>

          <el-form-item label="日期区间">
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              format="YYYY-MM-DD"
              value-format="YYYYMMDD"
              :clearable="false"
            />
          </el-form-item>

          <el-form-item label="输出格式">
            <el-radio-group v-model="form.output_format">
              <el-radio-button label="json">JSON</el-radio-button>
              <el-radio-button label="markdown">Markdown</el-radio-button>
            </el-radio-group>
          </el-form-item>

          <el-form-item label="horizons">
            <el-select v-model="form.horizons" multiple placeholder="选择 horizon">
              <el-option v-for="item in horizonOptions" :key="item" :label="`${item}d`" :value="item" />
            </el-select>
          </el-form-item>

          <el-form-item label="调仓频率">
            <el-radio-group v-model="form.rebalance_frequency">
              <el-radio-button label="D">日频</el-radio-button>
              <el-radio-button label="W">周频</el-radio-button>
              <el-radio-button label="M">月频</el-radio-button>
            </el-radio-group>
          </el-form-item>

          <el-form-item label="分组数">
            <el-input-number v-model="form.groups" :min="2" :max="10" controls-position="right" />
          </el-form-item>

          <el-form-item label="TopN">
            <el-input-number v-model="form.top_n" :min="1" :max="50" controls-position="right" />
          </el-form-item>

          <el-form-item label="最小横截面样本">
            <el-input-number v-model="form.min_cross_section" :min="2" :max="100" controls-position="right" />
          </el-form-item>

          <el-form-item label="权重模式">
            <el-radio-group v-model="form.weighting">
              <el-radio-button label="equal">等权</el-radio-button>
              <el-radio-button label="score">分数加权</el-radio-button>
            </el-radio-group>
          </el-form-item>

          <el-form-item label="交易成本 (bps)">
            <el-input-number v-model="form.transaction_cost_bps" :min="0" :max="500" controls-position="right" />
          </el-form-item>

          <el-form-item label="基准">
            <el-select v-model="form.benchmark">
              <el-option label="equal_weight_universe" value="equal_weight_universe" />
              <el-option label="buy_hold_universe_average" value="buy_hold_universe_average" />
            </el-select>
          </el-form-item>
        </div>
      </el-form>
    </el-card>

    <el-alert
      v-if="errorMessage"
      class="section-gap"
      type="error"
      :closable="false"
      show-icon
      :title="errorMessage"
    />

    <div v-if="report" class="results-stack">
      <el-card class="page-card">
        <template #header>
          <div class="section-title">研究配置</div>
        </template>
        <div class="summary-grid">
          <div class="summary-item"><span class="k">标题</span><span class="v">{{ report.title || 'Alpha Research Report' }}</span></div>
          <div class="summary-item"><span class="k">格式</span><span class="v">{{ report.output_format }}</span></div>
          <div class="summary-item"><span class="k">生成时间</span><span class="v">{{ report.generated_at || '—' }}</span></div>
          <div class="summary-item"><span class="k">股票池数量</span><span class="v">{{ report.config?.ticker_count ?? parsedTickers.length }}</span></div>
          <div class="summary-item"><span class="k">因子数</span><span class="v">{{ report.config?.factors?.length || 0 }}</span></div>
          <div class="summary-item"><span class="k">有效样本占比</span><span class="v">{{ formatPercent(report.dataset?.valid_sample_ratio) }}</span></div>
        </div>
      </el-card>

      <el-card v-if="report.factor_summaries?.length" class="page-card">
        <template #header>
          <div class="section-title">因子 IC 表</div>
        </template>
        <el-table :data="report.factor_summaries" stripe table-layout="auto">
          <el-table-column prop="factor_name" label="Factor" min-width="160" />
          <el-table-column prop="horizon" label="Horizon" min-width="90" />
          <el-table-column label="IC" min-width="100">
            <template #default="scope">{{ formatNumber(scope.row.ic_mean) }}</template>
          </el-table-column>
          <el-table-column label="RankIC" min-width="100">
            <template #default="scope">{{ formatNumber(scope.row.rank_ic_mean) }}</template>
          </el-table-column>
          <el-table-column label="ICIR" min-width="100">
            <template #default="scope">{{ formatNumber(scope.row.ic_ir) }}</template>
          </el-table-column>
          <el-table-column label="positive ratio" min-width="120">
            <template #default="scope">{{ formatPercent(scope.row.positive_ic_ratio) }}</template>
          </el-table-column>
          <el-table-column label="missing ratio" min-width="120">
            <template #default="scope">{{ formatPercent(scope.row.missing_ratio) }}</template>
          </el-table-column>
          <el-table-column label="Q5-Q1" min-width="120">
            <template #default="scope">{{ formatPercent(scope.row.group_long_short_return) }}</template>
          </el-table-column>
          <el-table-column prop="verdict" label="Verdict" min-width="120">
            <template #default="scope">
              <el-tag :type="verdictType(scope.row.verdict)" effect="dark">{{ scope.row.verdict }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <div class="chart-grid">
        <el-card class="page-card">
          <template #header>
            <div class="section-title">分组收益图（表）</div>
          </template>
          <div v-if="selectedGroupReturns.length" class="group-bars">
            <div v-for="item in selectedGroupReturns" :key="item.label" class="group-bar-row">
              <div class="group-label">{{ item.label }}</div>
              <div class="group-track">
                <div class="group-bar" :style="barStyle(item.value)"></div>
              </div>
              <div class="group-value">{{ formatPercent(item.value) }}</div>
            </div>
          </div>
          <el-empty v-else description="暂无分组收益数据" />
        </el-card>

        <el-card class="page-card">
          <template #header>
            <div class="section-title">TopN 回测图（摘要）</div>
          </template>
          <div v-if="report.topn_strategy" class="topn-metrics">
            <div class="metric-item"><span class="k">总收益</span><span class="v">{{ formatPercent(report.topn_strategy.total_return) }}</span></div>
            <div class="metric-item"><span class="k">年化收益</span><span class="v">{{ formatPercent(report.topn_strategy.annual_return) }}</span></div>
            <div class="metric-item"><span class="k">最大回撤</span><span class="v">{{ formatPercent(report.topn_strategy.max_drawdown) }}</span></div>
            <div class="metric-item"><span class="k">Sharpe</span><span class="v">{{ formatNumber(report.topn_strategy.sharpe) }}</span></div>
            <div class="metric-item"><span class="k">Turnover</span><span class="v">{{ formatPercent(report.topn_strategy.turnover) }}</span></div>
            <div class="metric-item"><span class="k">vs 等权基准</span><span class="v">{{ formatPercent(report.topn_strategy.excess_return_vs_equal_weight) }}</span></div>
          </div>
          <div v-if="topnCurvePoints.length" class="curve-preview">
            <div class="curve-title">净值预览</div>
            <div class="curve-list">
              <span v-for="(value, idx) in topnCurvePoints" :key="idx" class="curve-pill">{{ formatNumber(value) }}</span>
            </div>
          </div>
          <div v-if="benchmarkCurvePoints.length" class="curve-preview">
            <div class="curve-title">等权基准预览</div>
            <div class="curve-list">
              <span v-for="(value, idx) in benchmarkCurvePoints" :key="idx" class="curve-pill muted-pill">{{ formatNumber(value) }}</span>
            </div>
          </div>
        </el-card>
      </div>

      <el-card v-if="report.conclusion" class="page-card">
        <template #header>
          <div class="section-title">结论</div>
        </template>
        <div class="conclusion-grid">
          <div>
            <div class="mini-title">推荐因子</div>
            <div class="tag-wrap">
              <el-tag v-for="item in report.conclusion.recommended_factors || []" :key="item" type="success" effect="dark">{{ item }}</el-tag>
              <span v-if="!(report.conclusion.recommended_factors || []).length" class="muted">暂无</span>
            </div>
          </div>
          <div>
            <div class="mini-title">观察因子</div>
            <div class="tag-wrap">
              <el-tag v-for="item in report.conclusion.watchlist_factors || []" :key="item" type="warning" effect="dark">{{ item }}</el-tag>
              <span v-if="!(report.conclusion.watchlist_factors || []).length" class="muted">暂无</span>
            </div>
          </div>
          <div>
            <div class="mini-title">弃用因子</div>
            <div class="tag-wrap">
              <el-tag v-for="item in report.conclusion.rejected_factors || []" :key="item" type="danger" effect="dark">{{ item }}</el-tag>
              <span v-if="!(report.conclusion.rejected_factors || []).length" class="muted">暂无</span>
            </div>
          </div>
        </div>
        <ul class="summary-list">
          <li v-for="(item, idx) in report.conclusion.summary || []" :key="idx">{{ item }}</li>
        </ul>
      </el-card>

      <el-card v-if="report.output_format === 'markdown' && report.markdown" class="page-card">
        <template #header>
          <div class="section-title">Markdown 报告</div>
        </template>
        <pre class="markdown-box">{{ report.markdown }}</pre>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { ElMessage } from 'element-plus';
import dayjs from 'dayjs';
import { getMeta, getFactors, runResearchReport } from '../api';

const horizonOptions = [5, 10, 20, 60, 120];
const loading = ref(false);
const errorMessage = ref('');
const report = ref(null);
const factorOptions = ref([]);
const dateRange = ref(['20240101', dayjs().format('YYYYMMDD')]);

const defaultForm = () => ({
  tickersText: 'sh600519\nsz000858',
  factors: ['momentum_20d'],
  horizons: [20],
  min_cross_section: 5,
  groups: 5,
  rebalance_frequency: 'W',
  top_n: 5,
  weighting: 'equal',
  transaction_cost_bps: 10,
  benchmark: 'equal_weight_universe',
  output_format: 'json',
});

const form = ref(defaultForm());

const parsedTickers = computed(() => (
  form.value.tickersText
    .split(/\r?\n|,|\s+/)
    .map((item) => item.trim())
    .filter(Boolean)
));

const firstFactorName = computed(() => report.value?.factor_summaries?.[0]?.factor_name || '');

const selectedFactorDetail = computed(() => {
  const name = firstFactorName.value;
  if (!name) return null;
  return report.value?.factor_details?.[name] || null;
});

const selectedGroupReturns = computed(() => {
  const source = selectedFactorDetail.value?.group_backtest?.group_return_by_group || {};
  return Object.entries(source).map(([label, value]) => ({ label, value: Number(value || 0) }));
});

const topnCurvePoints = computed(() => (report.value?.topn_strategy?.equity_curve || []).slice(0, 12));
const benchmarkCurvePoints = computed(() => (report.value?.topn_strategy?.benchmark_equity_curve || []).slice(0, 12));

const verdictType = (verdict) => {
  if (verdict === 'recommended') return 'success';
  if (verdict === 'rejected') return 'danger';
  return 'warning';
};

const formatNumber = (value) => {
  const num = Number(value);
  if (!Number.isFinite(num)) return '—';
  return num.toFixed(4);
};

const formatPercent = (value) => {
  const num = Number(value);
  if (!Number.isFinite(num)) return '—';
  return `${(num * 100).toFixed(2)}%`;
};

const barStyle = (value) => {
  const num = Number(value || 0);
  const width = `${Math.min(100, Math.max(8, Math.abs(num) * 100))}%`;
  return {
    width,
    background: num >= 0 ? 'linear-gradient(90deg, #0ecb81, #45e6a3)' : 'linear-gradient(90deg, #f6465d, #ff8798)',
  };
};

const loadDefaults = async () => {
  try {
    const [metaRes, factorRes] = await Promise.all([getMeta(), getFactors()]);
    const latestTradeDate = metaRes?.data?.latest_trade_date;
    if (latestTradeDate) {
      dateRange.value = ['20240101', latestTradeDate];
    }
    factorOptions.value = factorRes?.data?.factors || [];
    if (!form.value.factors.length && factorOptions.value.length) {
      form.value.factors = [factorOptions.value[0].name];
    }
  } catch (error) {
    console.error('load research defaults failed', error);
    ElMessage.warning('研究页初始化部分失败，仍可手动填写参数');
  }
};

const buildPayload = () => ({
  tickers: parsedTickers.value,
  start_date: dateRange.value[0],
  end_date: dateRange.value[1],
  factors: form.value.factors,
  horizons: form.value.horizons,
  min_cross_section: form.value.min_cross_section,
  groups: form.value.groups,
  rebalance_frequency: form.value.rebalance_frequency,
  top_n: form.value.top_n,
  weighting: form.value.weighting,
  transaction_cost_bps: form.value.transaction_cost_bps,
  benchmark: form.value.benchmark,
  output_format: form.value.output_format,
});

const runReport = async () => {
  errorMessage.value = '';
  if (!parsedTickers.value.length) {
    errorMessage.value = '请至少输入一个 ticker';
    return;
  }
  if (!form.value.factors.length) {
    errorMessage.value = '请至少选择一个因子';
    return;
  }
  if (!dateRange.value?.[0] || !dateRange.value?.[1]) {
    errorMessage.value = '请选择有效日期区间';
    return;
  }

  loading.value = true;
  try {
    const response = await runResearchReport(buildPayload());
    report.value = response?.data?.data || null;
    ElMessage.success('研究报告生成成功');
  } catch (error) {
    console.error(error);
    report.value = null;
    errorMessage.value = error?.apiMessage || '研究报告生成失败';
    ElMessage.error(errorMessage.value);
  } finally {
    loading.value = false;
  }
};

const resetForm = () => {
  form.value = defaultForm();
  report.value = null;
  errorMessage.value = '';
};

onMounted(async () => {
  await loadDefaults();
});
</script>

<style scoped>
.alpha-research-page {
  padding: 24px;
  background: #0b0e14;
  min-height: calc(100vh - 60px);
}

.page-card {
  background: #131722;
  border: 1px solid #2b3139;
  color: #d1d4dc;
  margin-bottom: 20px;
}

:deep(.page-card .el-card__header) {
  background: #161b26;
  border-bottom: 1px solid #2b3139;
}

:deep(.page-card .el-card__body) {
  background: #131722;
}

.header-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.title {
  font-size: 24px;
  font-weight: 700;
  color: #f5f7fa;
}

.subtitle {
  margin-top: 6px;
  color: #8b94a7;
}

.research-form {
  margin-top: 4px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px 20px;
}

.factor-option {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.factor-option-desc {
  color: #8b94a7;
  font-size: 12px;
}

.section-gap {
  margin: 0 24px 20px;
}

.results-stack {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: #f5f7fa;
}

.summary-grid,
.topn-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.summary-item,
.metric-item {
  background: #0f1420;
  border: 1px solid #2b3139;
  border-radius: 10px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.k {
  color: #8b94a7;
  font-size: 12px;
}

.v {
  color: #f5f7fa;
  font-weight: 600;
}

.chart-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}

.group-bars {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.group-bar-row {
  display: grid;
  grid-template-columns: 54px 1fr 88px;
  gap: 12px;
  align-items: center;
}

.group-label,
.group-value {
  color: #d1d4dc;
  font-weight: 600;
}

.group-track {
  height: 14px;
  background: #0f1420;
  border-radius: 999px;
  overflow: hidden;
  border: 1px solid #2b3139;
}

.group-bar {
  height: 100%;
  border-radius: 999px;
}

.curve-preview {
  margin-top: 18px;
}

.curve-title,
.mini-title {
  color: #8b94a7;
  font-size: 13px;
  margin-bottom: 8px;
}

.curve-list,
.tag-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.curve-pill {
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(14, 203, 129, 0.12);
  color: #8ff0c0;
  font-size: 12px;
}

.muted-pill {
  background: rgba(139, 148, 167, 0.14);
  color: #c4cad6;
}

.conclusion-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.summary-list {
  margin: 18px 0 0;
  padding-left: 18px;
  color: #d1d4dc;
}

.markdown-box {
  white-space: pre-wrap;
  word-break: break-word;
  background: #0f1420;
  color: #d1d4dc;
  border: 1px solid #2b3139;
  border-radius: 12px;
  padding: 16px;
  line-height: 1.6;
}

.muted {
  color: #8b94a7;
}

:deep(.el-form-item__label),
:deep(.el-radio-button__inner),
:deep(.el-select__placeholder),
:deep(.el-textarea__inner),
:deep(.el-input__inner),
:deep(.el-input-number__decrease),
:deep(.el-input-number__increase) {
  color: #d1d4dc;
}

:deep(.el-input__wrapper),
:deep(.el-textarea__inner),
:deep(.el-select__wrapper),
:deep(.el-input-number),
:deep(.el-radio-button__inner) {
  background: #0f1420;
  border-color: #2b3139;
  box-shadow: none;
}

:deep(.el-input-number__decrease),
:deep(.el-input-number__increase) {
  background: #161b26;
  border-color: #2b3139;
}

:deep(.el-table),
:deep(.el-table tr),
:deep(.el-table th.el-table__cell),
:deep(.el-table td.el-table__cell) {
  background: #131722;
  color: #d1d4dc;
  border-color: #2b3139;
}

:deep(.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell) {
  background: #101521;
}

:deep(.el-empty__description p) {
  color: #8b94a7;
}

@media (max-width: 960px) {
  .form-grid,
  .chart-grid,
  .summary-grid,
  .topn-metrics,
  .conclusion-grid {
    grid-template-columns: 1fr;
  }

  .header-row {
    flex-direction: column;
  }
}
</style>
