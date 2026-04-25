const { LEGAL_META, ABOUT_SECTIONS } = require("../../utils/legal-content");

Page({
  data: {
    meta: LEGAL_META,
    sections: ABOUT_SECTIONS,
  },

  onCopyEmail() {
    wx.setClipboardData({
      data: this.data.meta.contactEmail,
      success: () => {
        wx.showToast({ title: "邮箱已复制", icon: "none" });
      },
    });
  },
});
