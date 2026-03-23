const { clearSession, login, restoreSession } = require('./utils/auth');
const { acceptAgreement } = require('./services/api');

// 全局小程序实例
App({
  onLaunch() {
    // 启动时优先恢复本地缓存的登录态，减少用户重复登录
    const session = restoreSession();
    this.globalData.token = session.token;
    this.globalData.user = session.user;
  },

  globalData: {
    // 本地开发默认指向 FastAPI 服务
    apiBaseUrl: 'http://127.0.0.1:8000/api/v1',
    // 当前登录用户信息（后端返回）
    user: null,
    // 登录态 token（用于请求后端接口）
    token: '',
    // 当前共读关系与当前书籍
    pair: null,
    currentBook: null
  },

  // 将会话状态同步到全局与本地缓存
  setSession(sessionData) {
    this.globalData.token = sessionData.token;
    this.globalData.user = sessionData.user;
    wx.setStorageSync('token', sessionData.token);
    wx.setStorageSync('user', sessionData.user);
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
