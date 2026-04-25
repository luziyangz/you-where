const { clearSession, login, restoreSession } = require('./utils/auth');
const { acceptAgreement } = require('./services/api');

const API_BASE_URL_BY_ENV = {
  develop: 'https://www.nizaina.online/api/v2',
  trial: 'https://www.nizaina.online/api/v2',
  release: 'https://www.nizaina.online/api/v2'
};

const getMiniProgramEnvVersion = () => {
  try {
    const accountInfo = wx.getAccountInfoSync && wx.getAccountInfoSync();
    return (accountInfo && accountInfo.miniProgram && accountInfo.miniProgram.envVersion) || 'develop';
  } catch (error) {
    return 'develop';
  }
};

const resolveApiBaseUrl = () => {
  const overrideUrl = wx.getStorageSync('apiBaseUrlOverride');
  if (overrideUrl) {
    return {
      baseUrl: overrideUrl,
      envVersion: getMiniProgramEnvVersion(),
      source: 'override'
    };
  }

  const envVersion = getMiniProgramEnvVersion();
  return {
    baseUrl: API_BASE_URL_BY_ENV[envVersion] || API_BASE_URL_BY_ENV.develop,
    envVersion,
    source: 'env'
  };
};

// 全局小程序实例
App({
  applyApiBaseUrlConfig() {
    const apiConfig = resolveApiBaseUrl();
    this.globalData.apiBaseUrl = apiConfig.baseUrl;
    this.globalData.apiEnvVersion = apiConfig.envVersion;
    this.globalData.apiBaseUrlSource = apiConfig.source;
  },

  setApiBaseUrlOverride(overrideUrl) {
    if (!overrideUrl) {
      wx.removeStorageSync('apiBaseUrlOverride');
    } else {
      wx.setStorageSync('apiBaseUrlOverride', overrideUrl);
    }
    this.applyApiBaseUrlConfig();
  },

  onLaunch() {
    // 根据环境自动选择 API 地址，并允许本地覆盖地址用于联调
    this.applyApiBaseUrlConfig();

    // 启动时优先恢复本地缓存的登录态，减少用户重复登录
    const session = restoreSession();
    this.globalData.token = session.token;
    this.globalData.user = session.user;
  },

  globalData: {
    // 启动时会被 onLaunch 动态覆盖为当前环境对应地址
    apiBaseUrl: 'https://www.nizaina.online/api/v2',
    // 当前小程序环境（develop / trial / release）
    apiEnvVersion: 'develop',
    // API 地址来源（环境映射或本地覆盖）
    apiBaseUrlSource: 'env',
    // 当前登录用户信息（后端返回）
    user: null,
    // 登录态 token（用于请求后端接口）
    token: '',
    // 当前共读关系与当前书籍
    pair: null,
    currentBook: null,
    // 避免登录失效场景重复弹提示
    authExpiredNotified: false
  },

  // 将会话状态同步到全局与本地缓存
  setSession(sessionData) {
    this.globalData.token = sessionData.token;
    this.globalData.user = sessionData.user;
    this.globalData.authExpiredNotified = false;
    wx.setStorageSync('token', sessionData.token);
    wx.setStorageSync('user', sessionData.user);
  },

  // 统一处理登录失效：清理状态并给出一次友好提示
  handleAuthExpired(message) {
    if (this.globalData.authExpiredNotified) {
      return;
    }
    this.globalData.authExpiredNotified = true;
    this.logout();
    wx.showToast({
      title: message || '登录状态已失效，请重新登录',
      icon: 'none'
    });
  },

  // 执行登录，必要时补充协议确认
  async loginFlow() {
    const sessionData = await login();
    this.setSession(sessionData);

    if (sessionData.need_agreement) {
      await acceptAgreement();
      this.globalData.user = {
        ...sessionData.user,
        agreement_accepted_at: new Date().toISOString()
      };
      wx.setStorageSync('user', this.globalData.user);
    }

    return this.globalData.user;
  },

  // 清理登录态并回到未登录状态
  logout() {
    clearSession();
    this.globalData.user = null;
    this.globalData.token = '';
    this.globalData.pair = null;
    this.globalData.currentBook = null;
  }
});
