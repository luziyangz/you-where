/**
 * 复制到剪贴板（兼容隐私协议未授权时的失败提示）
 */

const copyToClipboard = (text, options = {}) => {
  const data = String(text || '').trim();
  const toastTitle = options.toastTitle || '已复制';
  if (!data) {
    wx.showToast({ title: '暂无可复制内容', icon: 'none' });
    return;
  }

  const runCopy = () => {
    wx.setClipboardData({
      data,
      success: () => {
        wx.showToast({ title: toastTitle, icon: 'none' });
      },
      fail: () => {
        wx.showToast({ title: '复制失败，请长按文字手动复制', icon: 'none' });
      }
    });
  };

  if (typeof wx.requirePrivacyAuthorize === 'function') {
    wx.requirePrivacyAuthorize({
      success: runCopy,
      fail: runCopy
    });
    return;
  }
  runCopy();
};

module.exports = {
  copyToClipboard
};
