Page({
  data: {},
  
  onTapPrivacy() {
    wx.showToast({
      title: '隐私政策',
      icon: 'none'
    });
  },
  
  onTapAgreement() {
    wx.showToast({
      title: '用户协议',
      icon: 'none'
    });
  },
  
  onTapAbout() {
    wx.showToast({
      title: '关于我们',
      icon: 'none'
    });
  }
});