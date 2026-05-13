import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const normalized = error;
    const code = String(error?.code || '');
    const message = String(error?.message || '');
    normalized.isTimeout = code === 'ECONNABORTED' || /timeout/i.test(message);
    normalized.isCanceled = axios.isCancel(error) || code === 'ERR_CANCELED' || /canceled|aborted/i.test(message);
    normalized.apiMessage = error?.response?.data?.message || error?.response?.data?.detail || message;
    return Promise.reject(normalized);
  }
);

export const getMeta = () => {
  return api.get('/meta');
};

export const pingMeta = () => {
  return api.get('/meta');
};

export const getSummary = (startDate, endDate) => {
  return api.get('/summary', {
    params: { start_date: startDate, end_date: endDate }
  });
};

export const submitSummaryTask = (startDate, endDate) => {
  return api.post('/summary/tasks', null, {
    params: { start_date: startDate, end_date: endDate },
    timeout: 10000,
  });
};

export const getSummaryTask = (taskId) => {
  return api.get(`/summary/tasks/${taskId}`, { timeout: 10000 });
};

export const getStockDetail = (ticker, startDate, endDate) => {
  return api.get(`/detail/${ticker}`, {
    params: { start_date: startDate, end_date: endDate }
  });
};

export const getConfig = () => {
  return api.get('/config');
};

export const updateConfig = (payload) => {
  return api.post('/config', payload);
};

// ===== 策略 API =====
export const getStrategies = () => {
  return api.get('/strategies');
};

export const getFactors = () => {
  return api.get('/factors');
};

export const runPortfolioBacktest = (payload) => {
  return api.post('/strategies/portfolio/backtest', payload);
};

export const runStrategyBacktest = (payload) => {
  return api.post('/strategies/backtest', payload);
};

// ===== MX 选股 API =====
export const submitXuanguTask = (payload) => {
  return api.post('/mx/xuangu/tasks', payload, { timeout: 10000 });
};

export const getXuanguTask = (taskId) => {
  return api.get(`/mx/xuangu/tasks/${taskId}`, { timeout: 10000 });
};

// ===== Alpha Research API =====
export const runResearchDatasetBuild = (payload) => {
  return api.post('/research/dataset/build', payload);
};

export const runResearchFactorIC = (payload) => {
  return api.post('/research/factor/ic', payload);
};

export const runResearchGroupBacktest = (payload) => {
  return api.post('/research/factor/group-backtest', payload);
};

export const runResearchTopNBacktest = (payload) => {
  return api.post('/research/topn-backtest', payload);
};

export const runResearchReport = (payload) => {
  return api.post('/research/report', payload, { timeout: 120000 });
};

export default api;
