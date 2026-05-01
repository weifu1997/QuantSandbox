import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
});

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

export default api;