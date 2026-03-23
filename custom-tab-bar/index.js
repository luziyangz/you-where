Component({
  data: {
    selected: 0,
    hasBook: false,
    hasPartner: false,
    list: [
      {
        pagePath: "/pages/partner/index",
        text: "结伴",
        icon: "icon-users",
        activeIcon: "icon-users-active"
      },
      {
        pagePath: "/pages/home/index",
        text: "共读",
        icon: "icon-book-open",
        activeIcon: "icon-book-open-active"
      },
      {
        pagePath: "/pages/bookstore/index",
        text: "书城",
        icon: "icon-shopping-bag",
        activeIcon: "icon-shopping-bag-active"
      },
      {
        pagePath: "/pages/profile/index",
        text: "我的",
        icon: "icon-user",
        activeIcon: "icon-user-active"
      }
    ]
  },
  observers: {
    'hasPartner': function(hasPartner) {
      this.setData({
        'list[0].text': hasPartner ? '伙伴' : '结伴'
      });
    }
  },
  methods: {
    switchTab(e) {
      const data = e.currentTarget.dataset
      const url = data.path
      wx.switchTab({ url })
    },
    onCenterBtnClick() {
      // 触发全局事件，让当前页面处理（比如弹出添加书籍或记一笔）
      wx.lin = wx.lin || {};
      if (typeof wx.lin.onCenterBtnClick === 'function') {
        wx.lin.onCenterBtnClick();
      } else {
        // 默认行为，可以发通知
        const pages = getCurrentPages();
        const currentPage = pages[pages.length - 1];
        if (currentPage && typeof currentPage.onCenterBtnClick === 'function') {
          currentPage.onCenterBtnClick();
        }
      }
    }
  }
})