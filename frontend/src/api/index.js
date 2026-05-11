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

// ===== 工作流 API =====
export const runLowValueWorkflow = (payload) => {
  return api.post('/workflows/low-value/run', payload);
};

export const runBottomConfirmWorkflow = (payload) => {
  return api.post('/workflows/bottom-confirm/run', payload);
};

export const listWorkflowRuns = (params = {}) => {
  return api.get('/workflows', { params });
};

export const getWorkflowRun = (runId) => {
  return api.get(`/workflows/${runId}`);
};

export const getBottomConfirmRun = (runId) => {
  return api.get(`/workflows/bottom-confirm/runs/${runId}`);
};

export const getWorkflowStep = (runId, stepCode) => {
  return api.get(`/workflows/${runId}/steps/${stepCode}`);
};

export const getWorkflowCandidates = (runId, status) => {
  return api.get(`/workflows/${runId}/candidates`, { params: status ? { status } : {} });
};

export const getWatchlist = (view = 'all') => {
  return api.get('/watchlist', { params: { view } });
};

export const getLatestWatchlist = () => {
  return api.get('/watchlist/latest');
};

export const updateWatchlistEntry = (entryId, payload) => {
  return api.patch(`/watchlist/${entryId}`, payload);
};

export const deleteWatchlistEntry = (entryId) => {
  return api.delete(`/watchlist/${entryId}`);
};

export const batchDeleteWatchlist = (ids) => {
  return api.post('/watchlist/batch-delete', { ids });
};

export const volumeVerify = (payload) => {
  return api.post('/workflows/volume-verify', payload);
};

export const leftSideRank = (payload) => {
  return api.post('/workflows/left-side-rank', payload);
};

export default api;
