const { requireLogin } = require('./auth-gate');

const openReportPage = (options = {}) => {
  if (!requireLogin({ message: '请先登录后再反馈' })) {
    return;
  }
  const app = getApp();
  app.globalData.pendingReportContext = {
    targetType: options.targetType || 'app',
    targetId: options.targetId || '',
    targetUserId: options.targetUserId || '',
    hint: (options.hint || '').slice(0, 120),
    snapshot: (options.snapshot || '').slice(0, 300)
  };
  wx.navigateTo({
    url: '/pages/report/index'
  });
};

module.exports = {
  openReportPage
};
