Page({
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