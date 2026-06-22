const HOME_TAB = '/pages/home/index';
const HISTORY_TAB = '/pages/reading-history/index';
const PROGRESS_TAB = '/pages/progress/index';
const PROFILE_TAB = '/pages/profile/index';

const isLoggedIn = () => {
  try {
    const app = getApp();
    return !!(app && app.globalData && app.globalData.token && app.globalData.user);
  } catch (error) {
    return false;
  }
};

Component({
  data: {
    selected: 0,
    hasBook: false,
    hasPartner: false,
    list: [
      {
        pagePath: HOME_TAB,
        text: "共读",
        icon: "icon-home"
      },
      {
        pagePath: HISTORY_TAB,
        text: "历史",
        icon: "icon-book"
      },
      {
        pagePath: PROGRESS_TAB,
        text: "我们的记录",
        icon: "icon-journal"
      },
      {
        pagePath: PROFILE_TAB,
        text: "我的",
        icon: "icon-profile"
      }
    ]
  },
  methods: {
    switchTab(e) {
      const data = e.currentTarget.dataset;
      const url = data.path;
      const index = Number(data.index);

      if (this.data.selected === index) {
        return;
      }

      wx.switchTab({ url });
    },
    onCenterBtnClick() {
      if (!isLoggedIn()) {
        wx.showToast({
          title: '请先登录后记录',
          icon: 'none'
        });
        return;
      }

      const pages = getCurrentPages();
      const currentPage = pages[pages.length - 1];
      if (currentPage && typeof currentPage.onCenterBtnClick === 'function') {
        currentPage.onCenterBtnClick();
        return;
      }

      const app = getApp();
      if (!this.data.hasPartner && !(app.globalData && app.globalData.pair)) {
        wx.navigateTo({
          url: '/pages/partner/index'
        });
        return;
      }
      if (this.data.hasBook || (app.globalData && app.globalData.currentBook)) {
        app.globalData.openProgressComposer = true;
        wx.switchTab({ url: PROGRESS_TAB });
        return;
      }
      wx.switchTab({ url: HISTORY_TAB });
    }
  }
})
