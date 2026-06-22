/**
 * 小程序内打开外部 HTTPS 链接。
 * web-view 域名须在微信公众平台配置「业务域名」；未在白名单内的链接走复制到浏览器。
 */

const WEBVIEW_HOST_WHITELIST = new Set([
  'www.gutenberg.org',
  'gutenberg.org',
  'gutendex.com',
  'zh.wikisource.org',
  'www.nizaina.online',
  'nizaina.online',
  'book.douban.com'
]);

const parseUrl = (raw) => {
  const text = String(raw || '').trim();
  if (!text) {
    return null;
  }
  const match = text.match(/^https?:\/\/([^/?#]+)/i);
  if (!match) {
    return null;
  }
  const host = String(match[1] || '').toLowerCase();
  const protocol = text.toLowerCase().startsWith('https://') ? 'https' : 'http';
  return { url: text, host, protocol };
};

const canOpenInWebView = (url) => {
  const parsed = parseUrl(url);
  if (!parsed || parsed.protocol !== 'https') {
    return false;
  }
  return WEBVIEW_HOST_WHITELIST.has(parsed.host);
};

const copyExternalLink = (url, toastTitle) => {
  wx.setClipboardData({
    data: String(url),
    success: () => {
      wx.showToast({
        title: toastTitle || '链接已复制',
        icon: 'none'
      });
    }
  });
};

/**
 * 优先在小程序 web-view 内打开；否则提示复制到浏览器。
 */
const openExternalLink = (url, options = {}) => {
  const raw = String(url || '').trim();
  if (!raw) {
    wx.showToast({ title: '链接不可用', icon: 'none' });
    return;
  }

  if (canOpenInWebView(raw)) {
    const title = encodeURIComponent(String(options.title || '外部页面').slice(0, 40));
    wx.navigateTo({
      url: `/pages/webview/index?url=${encodeURIComponent(raw)}&title=${title}`
    });
    return;
  }

  wx.showModal({
    title: options.modalTitle || '打开链接',
    content: options.modalContent || '该链接暂未接入小程序内浏览，可复制后在手机浏览器中打开。',
    confirmText: '复制链接',
    cancelText: '取消',
    success: (res) => {
      if (res.confirm) {
        copyExternalLink(raw, '链接已复制，请在浏览器打开');
      }
    }
  });
};

module.exports = {
  WEBVIEW_HOST_WHITELIST,
  canOpenInWebView,
  openExternalLink,
  copyExternalLink
};
