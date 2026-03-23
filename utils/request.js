// 统一封装 wx.request，负责携带 token、统一处理后端响应结构
const DEFAULT_BASE_URL = 'http://127.0.0.1:8000/api/v1';

const makeClientRequestId = () => {
  return `mini_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`;
};

const getBaseUrl = () => {
  const app = getApp();
  return (app && app.globalData && app.globalData.apiBaseUrl) || DEFAULT_BASE_URL;
};

const request = (options) => {
  return new Promise((resolve, reject) => {
    const token = wx.getStorageSync('token') || '';

    const method = (options.method || 'GET').toUpperCase();
    // wx.request 在部分版本/平台下不会自动序列化 JSON，显式 stringify 保证格式正确
    const isBodyMethod = method !== 'GET' && method !== 'HEAD';
    const rawData = options.data || {};
    const requestData = isBodyMethod ? JSON.stringify(rawData) : rawData;

    wx.request({
      url: `${getBaseUrl()}${options.url}`,
      method,
      data: requestData,
      timeout: options.timeout || 10000,
      header: {
        'Content-Type': 'application/json',
        'X-Request-Id': makeClientRequestId(),
        Authorization: token ? `Bearer ${token}` : '',
        ...(options.header || {})
      },
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300 && res.data && res.data.code === 0) {
          resolve(res.data.data);
          return;
        }

        if (res.statusCode === 401) {
          reject({
            code: 401,
            message: res.data?.message || '登录状态已失效，请重新登录'
          });
          return;
        }

        reject({
          code: res.data?.code || res.statusCode,
          message: res.data?.message || '请求失败'
        });
      },
      fail(err) {
        reject({
          code: -1,
          message: '网络异常，请稍后重试',
          detail: err
        });
      }
    });
  });
};

module.exports = {
  request,
  makeClientRequestId
};

