<template>
  <div class="detail-container">
    <section class="hero-card" v-loading="loading">
      <div class="header">
        <el-button @click="goBack" type="info" plain :icon="ArrowLeft">返回总览</el-button>

        <div class="title-block">
          <div class="title-row">
            <h2 class="ticker-title">
              <span class="stock-name">{{ stockName || ticker }}</span>
              <span class="ticker-code">{{ ticker }}</span>
            </h2>
            <span class="strategy-badge">{{ metadata.strategy_name || 'target_weight_demo' }}</span>
          </div>
          <div class="subtitle-row">
            <span>回测区间 {{ rangeLabel }}</span>
            <span v-if="metadata.data_source">数据源 {{ metadata.data_source }}</span>
          </div>
        </div>
      </div>

      <div class="stats-panel" v-if="metadata.total_return !== undefined">
        <div class="stat-box">
          <div class="stat-label">期末净值</div>
          <div class="stat-value" :class="Number(metadata.total_return) >= 0 ? 'red' : 'green'">¥{{ metadata.final_equity ?? '--' }}</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">累计收益率</div>
          <div class="stat-value" :class="Number(metadata.total_return) >= 0 ? 'red' : 'green'">{{ metadata.total_return ?? '--' }}%</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">最大回撤</div>
          <div class="stat-value green">{{ metadata.max_drawdown ?? '--' }}%</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">夏普比率</div>
          <div class="stat-value">{{ metadata.sharpe_ratio ?? '--' }}</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">交易胜率</div>
          <div class="stat-value">{{ formatWinRate(metadata) }}</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">盈亏比</div>
          <div class="stat-value">{{ formatPnlRatio(metadata) }}</div>
        </div>
      </div>
    </section>

    <section class="charts-wrapper" v-loading="loading">
      <div class="section-head">
        <div>
          <h3 class="section-title">价格与净值曲线</h3>
          <div class="section-note">逐步揭晓交易信号，查看价格与账户净值的联动</div>
        </div>
      </div>
      <div ref="klineChartRef" class="main-chart"></div>
      <div ref="equityChartRef" class="sub-chart"></div>
      <div ref="chartTooltipRef" class="chart-tooltip"></div>
    </section>

    <section class="logs-wrapper" v-loading="loading">
      <div class="section-head">
        <div>
          <h3 class="section-title">📝 已触发交易日志</h3>
          <div class="section-note">{{ logViewMode === 'trade' ? `当前显示 ${tradeViewLogs.length} 笔成交记录` : `当前显示 ${visibleLogs.length} 笔（总日志 ${logs.length} 笔）` }}</div>
        </div>
        <div class="log-toolbar">
          <el-segmented v-model="logViewMode" :options="logViewOptions" />
          <el-switch
            v-if="logViewMode === 'debug'"
            v-model="showAllLogs"
            inline-prompt
            active-text="显示全部日志"
            inactive-text="只看成交"
          />
        </div>
      </div>

      <el-table v-if="logViewMode === 'trade'" :data="tradeViewLogs" style="width: 100%" height="250" class="dark-table" size="small">
        <el-table-column prop="execution_date" label="成交日期" width="110">
          <template #default="scope">{{ formatDate(scope.row.execution_date) }}</template>
        </el-table-column>
        <el-table-column label="动作" width="80">
          <template #default="scope">
            <el-tag :type="actionTagType(scope.row.action)" size="small" effect="dark">{{ tradeActionLabel(scope.row.action) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="price" label="成交价" width="90">
          <template #default="scope">{{ formatNum(scope.row.price) }}</template>
        </el-table-column>
        <el-table-column prop="shares" label="成交股数" width="100">
          <template #default="scope">{{ formatNum(scope.row.shares) }}</template>
        </el-table-column>
        <el-table-column label="成交金额" width="110">
          <template #default="scope">{{ formatNum(calcTradeAmount(scope.row)) }}</template>
        </el-table-column>
        <el-table-column label="手续费" width="100">
          <template #default="scope">{{ formatNum(calcFee(scope.row)) }}</template>
        </el-table-column>
        <el-table-column prop="cash_after" label="成交后现金" width="110">
          <template #default="scope">{{ formatNum(scope.row.cash_after) }}</template>
        </el-table-column>
        <el-table-column label="仓位变化" width="120">
          <template #default="scope">{{ formatWeightTransition(scope.row.current_weight, scope.row.target_weight) }}</template>
        </el-table-column>
        <el-table-column prop="reason" label="说明" min-width="160">
          <template #default="scope">{{ humanizeReason(scope.row.reason) }}</template>
        </el-table-column>
      </el-table>

      <el-table v-else :data="visibleLogs" style="width: 100%" height="250" class="dark-table" size="small">
        <el-table-column prop="signal_date" label="信号日期" width="110">
          <template #default="scope">{{ formatDate(scope.row.signal_date) }}</template>
        </el-table-column>
        <el-table-column prop="execution_date" label="成交日期" width="110">
          <template #default="scope">{{ formatDate(scope.row.execution_date) }}</template>
        </el-table-column>
        <el-table-column label="动作" width="70">
          <template #default="scope">
            <el-tag :type="actionTagType(scope.row.action)" size="small" effect="dark">{{ scope.row.action || '--' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="target_weight" label="目标权重" width="90">
          <template #default="scope">{{ formatWeight(scope.row.target_weight) }}</template>
        </el-table-column>
        <el-table-column prop="current_weight" label="当前权重" width="90">
          <template #default="scope">{{ formatWeight(scope.row.current_weight) }}</template>
        </el-table-column>
        <el-table-column prop="price" label="成交价" width="90">
          <template #default="scope">{{ formatNum(scope.row.price) }}</template>
        </el-table-column>
        <el-table-column prop="shares" label="股数" width="90">
          <template #default="scope">{{ formatNum(scope.row.shares) }}</template>
        </el-table-column>
        <el-table-column prop="commission" label="佣金" width="90">
          <template #default="scope">{{ formatNum(scope.row.commission) }}</template>
        </el-table-column>
        <el-table-column prop="tax" label="印花税" width="90">
          <template #default="scope">{{ formatNum(scope.row.tax) }}</template>
        </el-table-column>
        <el-table-column prop="total_equity_before" label="交易前权益" width="110">
          <template #default="scope">{{ formatNum(scope.row.total_equity_before) }}</template>
        </el-table-column>
        <el-table-column prop="total_equity_after" label="交易后权益" width="110">
          <template #default="scope">{{ formatNum(scope.row.total_equity_after) }}</template>
        </el-table-column>
        <el-table-column prop="cash_after" label="交易后现金" width="110">
          <template #default="scope">{{ formatNum(scope.row.cash_after) }}</template>
        </el-table-column>
        <el-table-column prop="reason" label="触发原因" min-width="140">
          <template #default="scope">{{ scope.row.reason || '--' }}</template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, computed } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { ArrowLeft } from '@element-plus/icons-vue';
import { getStockDetail } from '../api';
import { ElMessage } from 'element-plus';

const props = defineProps(['ticker']);
const router = useRouter();
const route = useRoute();

const loading = ref(true);
const metadata = ref({});
const resolveStockName = (data, ticker) => String(data?.display_name || data?.name || ticker || '').trim();

const stockName = ref('');
const rangeLabel = ref('--');

// 🌟 核心引擎内存：存放后端的全量数据
let fullKlineData = [];
let fullEquityData = [];
let fullMarkers = [];
let fullLogs = [];

const logs = ref([]);
const showAllLogs = ref(false);
const logViewMode = ref('trade');
const logViewOptions = [
  { label: '交易视图', value: 'trade' },
  { label: '调试视图', value: 'debug' },
];
const isTradeAction = (action) => {
  const normalized = String(action || '').toLowerCase();
  return normalized === 'buy' || normalized === 'sell' || normalized === '买入' || normalized === '卖出';
};
const tradeViewLogs = computed(() => logs.value.filter((log) => isTradeAction(log?.action)));
const visibleLogs = computed(() => {
  if (showAllLogs.value) return logs.value;
  return tradeViewLogs.value;
});
const totalDays = ref(0);

const klineChartRef = ref(null);
const equityChartRef = ref(null);
const chartTooltipRef = ref(null);
let klineChart = null;
let equityChart = null;
let candlestickSeries = null;
let areaSeries = null;

const goBack = () => router.push('/');

const normalizeDateKey = (value) => {
  if (!value) return '';
  const raw = String(value).trim();
  if (!raw) return '';
  const datePart = raw.includes('T') ? raw.split('T')[0] : raw.split(' ')[0];
  return datePart.replace(/\//g, '-');
};

const toBusinessDay = (value) => {
  const dateKey = normalizeDateKey(value);
  if (!dateKey) return null;
  const [year, month, day] = dateKey.split('-').map(Number);
  if (!year || !month || !day) return null;
  return { year, month, day };
};

const formatDate = (value) => normalizeDateKey(value) || '--';
const formatNum = (value) => {
  if (value === null || value === undefined || value === '') return '--';
  const num = Number(value);
  if (Number.isNaN(num)) return '--';
  if (Math.abs(num) < 0.01 && num !== 0) return num.toExponential(2);
  return num.toFixed(2);
};
const hasClosedTrades = (meta) => Boolean(meta?.has_closed_trades) || Number(meta?.closed_trade_count || meta?.trade_count || 0) > 0;
const formatWinRate = (meta) => {
  if (meta?.win_rate_display) return meta.win_rate_display;
  if (!hasClosedTrades(meta)) return '--';
  const formatted = formatNum(meta?.win_rate);
  return formatted === '--' ? '--' : `${formatted}%`;
};
const formatPnlRatio = (meta) => {
  if (meta?.pnl_ratio_display) return meta.pnl_ratio_display;
  if (!hasClosedTrades(meta)) return '--';
  return formatNum(meta?.pnl_ratio);
};
const formatWeight = (value) => {
  if (value === null || value === undefined || value === '') return '--';
  const num = Number(value);
  if (Number.isNaN(num)) return '--';
  return (num * 100).toFixed(1) + '%';
};
const actionTagType = (action) => {
  if (!action) return 'info';
  if (action === '买入' || action === 'buy') return 'danger';
  if (action === '卖出' || action === 'sell') return 'success';
  if (action === 'hold' || action === '持有') return 'warning';
  if (action === 'skipped' || action === '跳过') return 'info';
  return 'info';
};
const tradeActionLabel = (action) => {
  if (action === 'buy' || action === '买入') return '买入';
  if (action === 'sell' || action === '卖出') return '卖出';
  return action || '--';
};
const calcTradeAmount = (row) => Number(row?.price || 0) * Number(row?.shares || 0);
const calcFee = (row) => {
  const explicit = Number(row?.fee);
  if (!Number.isNaN(explicit) && explicit) return explicit;
  return Number(row?.commission || 0) + Number(row?.tax || 0);
};
const formatWeightTransition = (fromValue, toValue) => `${formatWeight(fromValue)} → ${formatWeight(toValue)}`;
const humanizeReason = (reason) => {
  const mapping = {
    target_weight_buy: '按目标仓位买入',
    target_weight_sell: '按目标仓位卖出',
    trade_value_too_small_for_lot: '差额不足一手，未调仓',
    sell_insufficient_shares_or_too_small: '可卖仓位不足一手，未调仓',
    limit_up_cannot_buy: '涨停无法买入',
    limit_down_cannot_sell: '跌停无法卖出',
    suspended: '停牌，未成交',
  };
  return mapping[reason] || reason || '--';
};
const lookupKlineByDateKey = (dateKey) => fullKlineData.find((item) => normalizeDateKey(item.timeKey || item.time) === dateKey) || null;

const darkThemeOptions = {
  layout: { background: { color: '#131722' }, textColor: '#d1d4dc' },
  grid: { vertLines: { color: '#2B3139' }, horzLines: { color: '#2B3139' } },
  timeScale: { timeVisible: false, secondsVisible: false, borderColor: '#2B3139' },
  rightPriceScale: { borderColor: '#2B3139' }
};

// 🌟 一次性加载全部数据到图表
const loadAllData = () => {
  if (!candlestickSeries || !areaSeries) return;

  // 全部 K 线和净值数据
  candlestickSeries.setData(fullKlineData);
  areaSeries.setData(fullEquityData);

  // 全部 Markers
  if (typeof candlestickSeries.setMarkers === 'function') {
    candlestickSeries.setMarkers(fullMarkers);
  }

  // 全部日志
  logs.value = fullLogs;

  // 让时间轴显示全部
  klineChart.timeScale().fitContent();
};

const initChartAndData = async () => {
  try {
    const start = route.query.start || route.query.start_date || '20240101';
    const end = route.query.end || route.query.end_date || '20240131';
    rangeLabel.value = `${start} ~ ${end}`;
    
    const res = await getStockDetail(props.ticker, start, end);
    const data = res.data;
    metadata.value = data.metadata;
    stockName.value = resolveStockName(data, props.ticker);
    fullLogs = (data.logs || []).map(log => ({
      ...log,
      signal_date: formatDate(log.signal_date || log.timestamp),
      execution_date: formatDate(log.execution_date || log.timestamp),
    }));

    const seenDates = new Set();
    data.klines.forEach(item => {
      if (item.date && !seenDates.has(item.date)) {
        const businessDay = toBusinessDay(item.date);
        if (!businessDay) return;
        seenDates.add(normalizeDateKey(item.date));
        fullKlineData.push({ time: businessDay, timeKey: normalizeDateKey(item.date), open: Number(item.open), high: Number(item.high), low: Number(item.low), close: Number(item.close), volume: Number(item.volume), total_equity: Number(item.total_equity) });
        fullEquityData.push({ time: businessDay, timeKey: normalizeDateKey(item.date), value: Number(item.total_equity) });
      }
    });

    fullLogs.forEach(log => {
      const markerDate = normalizeDateKey(log.execution_date || log.timestamp);
      if (seenDates.has(markerDate)) {
        const businessDay = toBusinessDay(markerDate);
        if (!businessDay) return;
        const actionLower = String(log.action || '').toLowerCase();
        const isBuy = actionLower === 'buy' || actionLower === '买入';
        const isSell = actionLower === 'sell' || actionLower === '卖出';
        if (!isBuy && !isSell) return;
        fullMarkers.push({
          time: businessDay,
          timeKey: markerDate,
          position: isBuy ? 'belowBar' : 'aboveBar',
          color: isBuy ? '#F6465D' : '#0ECB81',
          shape: isBuy ? 'arrowUp' : 'arrowDown',
          text: isBuy ? '买入' : '卖出',
        });
      }
    });

    fullKlineData.sort((a, b) => normalizeDateKey(a.time).localeCompare(normalizeDateKey(b.time)));
    fullEquityData.sort((a, b) => normalizeDateKey(a.time).localeCompare(normalizeDateKey(b.time)));
    fullMarkers.sort((a, b) => normalizeDateKey(a.time).localeCompare(normalizeDateKey(b.time)));

    totalDays.value = fullKlineData.length;
    logs.value = fullLogs;

    await nextTick();
    
    const { createChart } = await import('lightweight-charts');
    klineChart = createChart(klineChartRef.value, { ...darkThemeOptions, width: klineChartRef.value.clientWidth, height: 400 });
    candlestickSeries = klineChart.addCandlestickSeries({ upColor: '#F6465D', downColor: '#0ECB81', borderVisible: false, wickUpColor: '#F6465D', wickDownColor: '#0ECB81' });

    equityChart = createChart(equityChartRef.value, { ...darkThemeOptions, width: equityChartRef.value.clientWidth, height: 200 });
    areaSeries = equityChart.addAreaSeries({ topColor: 'rgba(245, 158, 11, 0.4)', bottomColor: 'rgba(245, 158, 11, 0.0)', lineColor: '#f59e0b', lineWidth: 2 });

    let syncingFromKline = false;
    let syncingFromEquity = false;
    klineChart.timeScale().subscribeVisibleLogicalRangeChange(timeRange => {
      if (!timeRange || syncingFromEquity) return;
      syncingFromKline = true;
      equityChart.timeScale().setVisibleLogicalRange(timeRange);
      syncingFromKline = false;
    });
    equityChart.timeScale().subscribeVisibleLogicalRangeChange(timeRange => {
      if (!timeRange || syncingFromKline) return;
      syncingFromEquity = true;
      klineChart.timeScale().setVisibleLogicalRange(timeRange);
      syncingFromEquity = false;
    });

    const tooltip = chartTooltipRef.value;
    const hideTooltip = () => {
      if (!tooltip) return;
      tooltip.style.opacity = '0';
    };
    const showTooltip = (param) => {
      if (!tooltip || !param?.point || !param?.time) return;
      const candle = param.seriesData?.get(candlestickSeries);
      const equity = param.seriesData?.get(areaSeries);
      if (!candle && !equity) {
        hideTooltip();
        return;
      }
      const dateText = normalizeDateKey(param.time?.year ? `${param.time.year}-${String(param.time.month).padStart(2, '0')}-${String(param.time.day).padStart(2, '0')}` : param.time);
      const kline = lookupKlineByDateKey(dateText);
      const open = kline ? Number(kline.open) : (candle ? Number(candle.open) : null);
      const high = kline ? Number(kline.high) : (candle ? Number(candle.high) : null);
      const low = kline ? Number(kline.low) : (candle ? Number(candle.low) : null);
      const close = kline ? Number(kline.close) : (candle ? Number(candle.close) : null);
      const volume = kline && kline.volume !== undefined ? Number(kline.volume) : null;
      const pct = kline && open && open !== 0 ? ((close - open) / open) * 100 : (candle && open && open !== 0 ? ((close - open) / open) * 100 : null);
      const equityValue = kline && kline.total_equity !== undefined ? Number(kline.total_equity) : (equity && equity.value !== undefined ? Number(equity.value) : null);
      tooltip.innerHTML = `
        <div class="tooltip-date">${dateText || '--'}</div>
        <div class="tooltip-row"><span class="k">开盘</span><span class="v ${open !== null && close !== null && close >= open ? 'green' : 'red'}">${open !== null ? open.toFixed(2) : '...'}</span></div>
        <div class="tooltip-row"><span class="k">收盘</span><span class="v ${open !== null && close !== null && close >= open ? 'green' : 'red'}">${close !== null ? close.toFixed(2) : '...'}</span></div>
        <div class="tooltip-row"><span class="k">最高</span><span class="v">${high !== null ? high.toFixed(2) : '...'}</span></div>
        <div class="tooltip-row"><span class="k">最低</span><span class="v">${low !== null ? low.toFixed(2) : '...'}</span></div>
        <div class="tooltip-sep"></div>
        <div class="tooltip-row"><span class="k">成交量</span><span class="v">${volume !== null ? volume.toLocaleString('zh-CN') : '...'}</span></div>
        <div class="tooltip-row tooltip-row-2col"><span class="k">净值</span><span class="v tooltip-right ${equityValue !== null && equityValue >= 0 ? 'green' : 'red'}">${equityValue !== null ? equityValue.toFixed(2) : '...'}</span></div>
        <div class="tooltip-row tooltip-row-2col"><span class="k">涨跌</span><span class="v tooltip-right ${pct !== null && pct >= 0 ? 'green' : 'red'}">${pct !== null ? `${pct.toFixed(2)}%` : '...'}</span></div>
      `;
      tooltip.style.opacity = '1';
      const chartRect = klineChartRef.value.getBoundingClientRect();
      const x = Math.min(Math.max(param.point.x + 16, 12), Math.max(chartRect.width - 220, 12));
      const y = Math.min(Math.max(param.point.y - 12, 12), Math.max(chartRect.height - 110, 12));
      tooltip.style.left = `${x}px`;
      tooltip.style.top = `${y}px`;
    };
    klineChart.subscribeCrosshairMove((param) => {
      if (!param || param.time === undefined) {
        hideTooltip();
        return;
      }
      showTooltip(param);
    });
    equityChart.subscribeCrosshairMove((param) => {
      if (!param || param.time === undefined) {
        hideTooltip();
        return;
      }
      showTooltip(param);
    });

    // 首次渲染全部
    loadAllData();

  } catch (error) {
    ElMessage.error('图表渲染失败，请检查控制台报错');
    console.error(error);
  } finally {
    loading.value = false;
  }
};

onMounted(() => initChartAndData());

onUnmounted(() => {
  if (klineChart) klineChart.remove();
  if (equityChart) equityChart.remove();
});
</script>

<style scoped>
.detail-container {
  background: linear-gradient(180deg, #0b0e14 0%, #0f131a 100%);
  min-height: 100vh;
  padding: 20px;
  color: #d1d4dc;
}
.hero-card,
.charts-wrapper,
.logs-wrapper {
  background-color: #131722;
  border: 1px solid #2b3139;
  border-radius: 14px;
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.18);
}
.hero-card { padding: 18px; margin-bottom: 18px; }
.header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 15px; flex-wrap: wrap; gap: 15px; }
.title-block { display: flex; flex-direction: column; gap: 8px; min-width: 220px; flex: 1; }
.title-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.ticker-title { margin: 0; color: #fff; font-size: 24px; font-weight: 700; line-height: 1.2; display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.stock-name { font-size: 24px; font-weight: 700; color: #fff; }
.ticker-code { font-size: 14px; font-weight: 400; color: #8a919e; }
.strategy-badge { display: inline-flex; align-items: center; height: 28px; padding: 0 10px; border-radius: 999px; background: rgba(14, 203, 129, 0.12); color: #0ecb81; border: 1px solid rgba(14, 203, 129, 0.35); font-size: 12px; }
.subtitle-row { display: flex; gap: 14px; flex-wrap: wrap; color: #8a919e; font-size: 12px; }
.stats-panel { display: flex; flex-wrap: wrap; gap: 12px; padding-top: 4px; }
.stat-box { flex: 1; min-width: 120px; display: flex; flex-direction: column; align-items: center; justify-content: center; background: #1a1e29; border: 1px solid #2b3139; border-radius: 12px; padding: 12px 10px; }
.stat-label { font-size: 12px; color: #8a919e; margin-bottom: 6px; }
.stat-value { font-size: 18px; font-weight: 700; color: #fff; }
.section-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 12px; }
.section-title { margin: 0; font-size: 16px; color: #fff; }
.section-note { margin-top: 4px; font-size: 12px; color: #8a919e; }
.charts-wrapper { position: relative; padding: 16px; margin-bottom: 18px; }
.main-chart { width: 100%; border-bottom: 1px solid #2B3139; margin-bottom: 12px; padding-bottom: 12px; }
.sub-chart { width: 100%; }
.chart-tooltip { position: absolute; z-index: 10; pointer-events: none; opacity: 0; width: 140px; background: rgba(11, 14, 20, 0.96); border: 1px solid #2b3139; border-radius: 12px; padding: 9px 10px; box-shadow: 0 10px 24px rgba(0, 0, 0, 0.35); color: #d1d4dc; font-size: 12px; line-height: 1.45; backdrop-filter: blur(4px); }
.chart-tooltip .tooltip-date { color: #fff; font-weight: 800; margin-bottom: 6px; font-size: 13px; }
.chart-tooltip .tooltip-row { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; margin: 3px 0; }
.chart-tooltip .tooltip-row-2col .k { min-width: 32px; }
.chart-tooltip .tooltip-row-2col .v { text-align: right; flex: 1; }
.chart-tooltip .tooltip-row .k { color: #8a919e; font-size: 11px; }
.chart-tooltip .tooltip-row .v { font-size: 13px; font-weight: 700; color: #d1d4dc; }
.chart-tooltip .tooltip-row .v.red { color: #F6465D !important; }
.chart-tooltip .tooltip-row .v.green { color: #0ECB81 !important; }
.chart-tooltip .tooltip-right { text-align: right; }
.chart-tooltip .tooltip-sep { height: 1px; background: #2b3139; margin: 6px 0; }
.logs-wrapper { padding: 16px; }
.log-toolbar { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.red { color: #F6465D !important; }
.green { color: #0ECB81 !important; }
.text-red { color: #F6465D; font-weight: bold; }
.text-green { color: #0ECB81; font-weight: bold; }
:deep(.el-table) { background-color: transparent !important; --el-table-border-color: #2B3139; --el-table-header-bg-color: #1a1e29; --el-table-tr-bg-color: #131722; --el-table-text-color: #d1d4dc; --el-table-header-text-color: #8a919e; }
:deep(.el-table th.el-table__cell), :deep(.el-table td.el-table__cell) { border-bottom: 1px solid #2B3139; }
:deep(.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell) { background-color: #1a1e29; }
@media (max-width: 960px) {
  .header { align-items: stretch; }
  .time-controls { align-items: stretch; width: 100%; }
  .section-head { flex-direction: column; }
  :deep(.el-button-group) { width: 100%; display: flex; }
  :deep(.el-button-group .el-button) { flex: 1; }
}
</style>
