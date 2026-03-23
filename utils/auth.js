const { request } = require('./request');

const STORAGE_KEYS = {
  token: 'token',
  user: 'user',
  debugOpenId: 'debug_open_id'
};

const getOrCreateDebugOpenId = () => {
  let debugOpenId = wx.getStorageSync(STORAGE_KEYS.debugOpenId);
  if (!debugOpenId) {
    debugOpenId = `debug_${Date.now()}_${Math.random().toString(16).slice(2, 10)}`;
    wx.setStorageSync(STORAGE_KEYS.debugOpenId, debugOpenId);
  }
  return debugOpenId;
};

const login = () => {
  return new Promise((resolve, reject) => {
    wx.login({
      success: async (res) => {
        if (!res.code) {
          reject(new Error('微信登录失败，请稍后重试'));
          return;
        }

        try {
          const data = await request({
            url: '/auth/login',
            method: 'POST',
            data: {
              code: res.code,
              debug_open_id: getOrCreateDebugOpenId()
            }
          });

          wx.setStorageSync(STORAGE_KEYS.token, data.token);
          wx.setStorageSync(STORAGE_KEYS.user, data.user);
          resolve(data);
        } catch (error) {
          reject(error);
        }
      },
      fail: reject
    });
  });
};

const clearSession = () => {
  wx.removeStorageSync(STORAGE_KEYS.token);
  wx.removeStorageSync(STORAGE_KEYS.user);
};

const restoreSession = () => {
  return {
    token: wx.getStorageSync(STORAGE_KEYS.token) || '',
    user: wx.getStorageSync(STORAGE_KEYS.user) || null
  };
};

module.exports = {
  login,
  clearSession,
  restoreSession
};
