Page({
  onLoad() {
    this.goHome();
  },

  onShow() {
    this.goHome();
  },

  onGoHome() {
    this.goHome();
  },

  goHome() {
    wx.switchTab({ url: '/pages/home/index' });
  }
});
