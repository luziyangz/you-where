const { fetchProfileMe, fetchProfileStats, updateMe } = require('../../services/api');
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
    },
    editingNickname: false,
    nicknameDraft: '',
    savingNickname: false
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

  noop() {},

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
      const [profileRes, stats] = await Promise.all([fetchProfileMe(), fetchProfileStats()]);
      const me = profileRes.user || null;
      const partner = profileRes.partner || null;
      app.globalData.user = me;
      app.globalData.pair = partner ? { partner } : null;

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

  onTapEditNickname() {
    if (!this.data.user) {
      return;
    }
    this.setData({
      editingNickname: true,
      nicknameDraft: this.data.user.nickname || ''
    });
  },

  onNicknameInput(e) {
    this.setData({ nicknameDraft: e.detail.value || '' });
  },

  onCancelEditNickname() {
    this.setData({
      editingNickname: false,
      nicknameDraft: ''
    });
  },

  async onSaveNickname() {
    const nickname = (this.data.nicknameDraft || '').trim();
    if (!nickname) {
      wx.showToast({ title: '请输入昵称', icon: 'none' });
      return;
    }
    this.setData({ savingNickname: true });
    try {
      const payload = await updateMe({ nickname });
      const updatedUser = payload.user || null;
      if (updatedUser) {
        app.globalData.user = updatedUser;
        wx.setStorageSync('user', updatedUser);
        this.setData({
          user: {
            ...this.data.user,
            ...updatedUser
          },
          editingNickname: false,
          nicknameDraft: ''
        });
      }
      wx.showToast({ title: '昵称已更新', icon: 'success' });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '更新失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ savingNickname: false });
    }
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
  },

  onTapReadingHistory() {
    wx.navigateTo({
      url: '/pages/reading-history/index'
    });
  },

  onTapReadingGoal() {
    wx.navigateTo({
      url: '/pages/reading-goal/index'
    });
  },

  onTapReminder() {
    wx.navigateTo({
      url: '/pages/reminder/index'
    });
  }
});