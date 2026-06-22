/**
 * 调用隐私敏感能力前检查是否需先同意《小程序隐私保护指引》
 */

const PENDING_TXT_IMPORT = 'bookstore_txt_import';

const canUseAgreePrivacyButton = () => {
  if (typeof wx.canIUse === 'function') {
    return wx.canIUse('button.open-type.agreePrivacyAuthorization');
  }
  return typeof wx.chooseMessageFile === 'function';
};

/**
 * 若需授权则跳转隐私页，否则执行 onReady（须在用户点击后调用）
 */
const runAfterPrivacyReady = (onReady, options = {}) => {
  const ready = typeof onReady === 'function' ? onReady : () => {};
  const scene = options.scene || PENDING_TXT_IMPORT;

  if (typeof wx.getPrivacySetting !== 'function') {
    ready();
    return;
  }

  wx.getPrivacySetting({
    success: (res) => {
      if (res && res.needAuthorization) {
        const app = getApp();
        if (app && app.globalData) {
          app.globalData.__privacyPendingScene = scene;
        }
        wx.navigateTo({
          url: `/pages/privacy-authorize/index?scene=${encodeURIComponent(scene)}`,
          fail: () => {
            wx.showModal({
              title: '需同意隐私指引',
              content: '请前往隐私授权页点击「同意隐私指引并继续」后，再试一次当前操作。',
              confirmText: '去授权',
              cancelText: '取消',
              success: (r) => {
                if (r.confirm) {
                  wx.navigateTo({ url: '/pages/privacy-authorize/index' });
                }
              }
            });
          }
        });
        return;
      }
      ready();
    },
    fail: () => ready()
  });
};

const consumePendingScene = (expected) => {
  const app = getApp();
  if (!app || !app.globalData) {
    return false;
  }
  const scene = app.globalData.__privacyPendingScene;
  if (scene !== expected) {
    return false;
  }
  app.globalData.__privacyPendingScene = '';
  return true;
};

const markPendingRetry = (scene) => {
  const app = getApp();
  if (app && app.globalData) {
    app.globalData.__privacyPendingScene = `${scene}_retry`;
  }
};

module.exports = {
  PENDING_TXT_IMPORT,
  canUseAgreePrivacyButton,
  runAfterPrivacyReady,
  consumePendingScene,
  markPendingRetry
};
