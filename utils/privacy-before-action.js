/**
 * 在调用隐私相关 API 前，引导用户到统一授权页完成「同意」。
 */

const PRIVACY_PAGE = '/pages/privacy-authorize/index';

const getPrivacySetting = () =>
  new Promise((resolve) => {
    if (typeof wx.getPrivacySetting !== 'function') {
      resolve({ needAuthorization: false, privacyContractName: '《小程序隐私保护指引》' });
      return;
    }
    wx.getPrivacySetting({
      success: (res) => {
        resolve({
          needAuthorization: !!res.needAuthorization,
          privacyContractName: res.privacyContractName || '《小程序隐私保护指引》'
        });
      },
      fail: () => {
        resolve({ needAuthorization: false, privacyContractName: '《小程序隐私保护指引》' });
      }
    });
  });

/**
 * 若尚未同意隐私指引，跳转授权页；已同意则直接执行 action。
 * @param {string} resumeKey 授权完成后由业务页 onShow 读取 app.globalData.__privacyResumeAction
 */
const runAfterPrivacyReady = async (resumeKey, action) => {
  const setting = await getPrivacySetting();
  if (!setting.needAuthorization) {
    if (typeof action === 'function') {
      action();
    }
    return false;
  }
  const app = getApp();
  app.globalData.__privacyResumeAction = resumeKey || '';
  wx.navigateTo({
    url: `${PRIVACY_PAGE}?resume=${encodeURIComponent(resumeKey || '')}`,
    fail: () => {
      app.globalData.__privacyResumeAction = '';
      wx.showToast({ title: '无法打开授权页，请稍后重试', icon: 'none' });
    }
  });
  return true;
};

const navigateToPrivacyAuthorize = (resumeKey) => {
  const app = getApp();
  app.globalData.__privacyResumeAction = resumeKey || '';
  wx.navigateTo({
    url: `${PRIVACY_PAGE}?resume=${encodeURIComponent(resumeKey || '')}`
  });
};

const consumePrivacyResume = (expectedKey) => {
  const app = getApp();
  const key = app.globalData.__privacyResumeAction || '';
  if (!key || (expectedKey && key !== expectedKey)) {
    return false;
  }
  app.globalData.__privacyResumeAction = '';
  return true;
};

module.exports = {
  getPrivacySetting,
  runAfterPrivacyReady,
  navigateToPrivacyAuthorize,
  consumePrivacyResume
};
