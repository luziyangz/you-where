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

const shouldUseDebugIdentity = () => {
  // 正式版必须使用真实微信登录态，禁止携带 debug_open_id，以符合微信平台规范与审核要求
  try {
    const accountInfo = wx.getAccountInfoSync && wx.getAccountInfoSync();
    const env = accountInfo && accountInfo.miniProgram && accountInfo.miniProgram.envVersion;
    if (env === 'release') {
      return false;
    }
  } catch (error) {
    // ignore
  }

  try {
    const systemInfo = wx.getSystemInfoSync && wx.getSystemInfoSync();
    if (systemInfo && systemInfo.platform === 'devtools') {
      return true;
    }
  } catch (error) {
    // ignore
  }

  try {
    const app = getApp && getApp();
    const baseUrl = (app && app.globalData && app.globalData.apiBaseUrl) || '';
    return /https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?/i.test(baseUrl);
  } catch (error) {
    return false;
  }
};

const buildLoginPayload = (code, extra = {}) => ({
  code,
  ...extra,
  ...(shouldUseDebugIdentity() ? { debug_open_id: getOrCreateDebugOpenId() } : {})
});

const wxLogin = () => {
  return new Promise((resolve, reject) => {
    wx.login({
      success: (res) => {
        if (!res.code) {
          reject(new Error('微信登录失败，请稍后重试'));
          return;
        }
        resolve(res.code);
      },
      fail: reject
    });
  });
};

const persistSession = (data) => {
  wx.setStorageSync(STORAGE_KEYS.token, data.token);
  wx.setStorageSync(STORAGE_KEYS.user, data.user);
  return data;
};

const isInvalidWechatCodeError = (error) => {
  const message = String((error && error.message) || '');
  return error && Number(error.code) === 40001 && /invalid code|登录凭证|code/i.test(message);
};

const login = async (options = {}) => {
  const code = await wxLogin();
  try {
    const data = await request({
      url: '/auth/login',
      method: 'POST',
      data: buildLoginPayload(code)
    });
    return persistSession(data);
  } catch (error) {
    if (!options.retryOnInvalidCode || !isInvalidWechatCodeError(error)) {
      throw error;
    }
    return login({ retryOnInvalidCode: false });
  }
};

const reviewLogin = async ({ account, password } = {}) => {
  const data = await request({
    url: '/auth/review-login',
    method: 'POST',
    data: {
      account: account || '',
      password: password || ''
    }
  });
  return persistSession(data);
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
  reviewLogin,
  clearSession,
  restoreSession
};
