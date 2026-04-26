const { requireLogin } = require('../../utils/auth-gate');

Page({
  onShow() {
    requireLogin({ message: '请先登录后进入设置' });
  },

  onTapPrivacy() {
    wx.navigateTo({
      url: '/pages/privacy-policy/index'
    });
  },
  
  onTapAgreement() {
    wx.navigateTo({
      url: '/pages/user-agreement/index'
    });
  },
  
  onTapAbout() {
    wx.navigateTo({
      url: '/pages/about-us/index'
    });
  }
});
