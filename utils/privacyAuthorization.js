/**
 * 全局注册 wx.onNeedPrivacyAuthorization：在未登录页等场景外触发隐私能力时，
 * 跳转统一授权页并在用户同意/拒绝后调用 resolve，符合微信基础库 2.32.3+ 要求。
 * 参考：https://developers.weixin.qq.com/miniprogram/dev/api/open-api/privacy/wx.onNeedPrivacyAuthorization.html
 */

function installPrivacyAuthorizationHost() {
  if (typeof wx.onNeedPrivacyAuthorization !== 'function') {
    return;
  }

  wx.onNeedPrivacyAuthorization((resolve, eventInfo) => {
    const app = getApp();
    // 覆盖式监听：新事件到达时先结束上一笔 pending，避免接口永久卡住
    if (typeof app.globalData.__privacyAuthResolve === 'function') {
      try {
        app.globalData.__privacyAuthResolve({ event: 'disagree' });
      } catch (e) {
        // ignore
      }
      app.globalData.__privacyAuthResolve = null;
    }

    app.globalData.__privacyAuthResolve = resolve;
    app.globalData.__privacyAuthReferrer = (eventInfo && eventInfo.referrer) || '';
    app.globalData.__privacyAuthHandled = false;

    const resume = app.globalData.__privacyResumeAction || '';
    const resumeQuery = resume ? `?resume=${encodeURIComponent(resume)}` : '';
    const targetUrl = `/pages/privacy-authorize/index${resumeQuery}`;

    wx.navigateTo({
      url: targetUrl,
      fail: () => {
        try {
          resolve({ event: 'disagree' });
        } catch (e) {
          // ignore
        }
        app.globalData.__privacyAuthResolve = null;
        wx.showToast({ title: '无法打开授权页，请从设置重试', icon: 'none' });
      }
    });
  });
}

module.exports = {
  installPrivacyAuthorizationHost
};
