const { request, makeClientRequestId } = require('../../utils/request');

const getV2BaseUrl = () => {
  const app = getApp();
  const baseUrl = (app && app.globalData && app.globalData.apiBaseUrl) || '';
  if (/\/api\/v1$/i.test(baseUrl)) {
    return baseUrl.replace(/\/api\/v1$/i, '/api/v2');
  }
  if (/\/api\/v2$/i.test(baseUrl)) {
    return baseUrl;
  }
  return `${baseUrl}/api/v2`;
};

const requestV2 = (options) => {
  return request({
    ...options,
    baseUrl: getV2BaseUrl()
  });
};

module.exports = {
  makeClientRequestId,
  requestV2
};
