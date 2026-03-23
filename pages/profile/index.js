const { fetchMe, fetchStats, fetchHome } = require('../../services/api');
const { formatApiError } = require('../../utils/copywriting');

const app = getApp();

Page({
  data: {
    isLogin: false,
    loginLoading: false,
    user: null,
    stats: {
      total_books: 0,
      total_pages: 0,
      total_entries: 0
    }
  },

  onShow() {
    this.initPage();
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({
        selected: 1,
        hasBook: !!app.globalData.currentBook,
        hasPartner: !!app.globalData.pair
      });
    }
  },

  async initPage() {
    if (!app.globalData.user || !app.globalData.token) {
      this.setData({
        isLogin: false,
        user: null,
        stats: {
          total_books: 0,
          total_pages: 0,
          total_entries: 0
        }
      });
      return;
    }

    await this.loadProfileData();
  },

  async loadProfileData() {
    try {
      const [me, stats] = await Promise.all([fetchMe(), fetchStats()]);
      app.globalData.user = me;
      
      let partner = null;
      if (app.globalData.pair) {
        partner = app.globalData.pair.partner;
      } else {
        // 联调阶段不做静默兜底，依赖后端接口完整返回关系数据
        const homeData = await fetchHome();
        app.globalData.pair = homeData.pair;
        if (homeData.pair) {
          partner = homeData.pair.partner;
        }
      }

      this.setData({
        isLogin: true,
        user: {
          ...me,
          partner
        },
        stats
      });
    } catch (error) {
      if (error.code === 401) {
        app.logout();
      }
      wx.showToast({
        title: formatApiError(error, '加载失败'),
        icon: 'none'
      });
    }
  },

  async onTapLogin() {
    this.setData({ loginLoading: true });
    try {
      await app.loginFlow();
      await this.loadProfileData();
      wx.showToast({
        title: '登录成功',
        icon: 'success'
      });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '登录失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ loginLoading: false });
    }
  },

  onCopyJoinCode() {
    if (!this.data.user || !this.data.user.join_code) {
      return;
    }
    wx.setClipboardData({
      data: this.data.user.join_code
    });
  },

  onTapLogout() {
    wx.showModal({
      title: '退出登录',
      content: '将清除本地登录状态，但不会删除云端共读数据。',
      success: (res) => {
        if (!res.confirm) {
          return;
        }
        app.logout();
        this.setData({
          isLogin: false,
          user: null,
          stats: {
            total_books: 0,
            total_pages: 0,
            total_entries: 0
          }
        });
        wx.showToast({
          title: '已退出登录',
          icon: 'success'
        });
      }
    });
  },

  onTapSettings() {
    wx.navigateTo({
      url: '/pages/settings/index'
    });
  }
});