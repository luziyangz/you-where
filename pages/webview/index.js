const { canOpenInWebView } = require('../../utils/open-link');

Page({
  data: {
    safeUrl: ''
  },

  onLoad(query) {
    const raw = query && query.url ? decodeURIComponent(query.url) : '';
    const title = query && query.title ? decodeURIComponent(query.title) : '外部页面';
    if (title) {
      wx.setNavigationBarTitle({ title: String(title).slice(0, 12) });
    }
    if (canOpenInWebView(raw)) {
      this.setData({ safeUrl: raw });
      return;
    }
    this.setData({ safeUrl: '' });
  },

  onBack() {
    wx.navigateBack({
      fail: () => wx.switchTab({ url: '/pages/home/index' })
    });
  }
});
