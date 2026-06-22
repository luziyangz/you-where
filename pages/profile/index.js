const { fetchProfileMe, fetchProfileStats, fetchReadingGoal, updateMe } = require('../../services/api');
const { formatApiError } = require('../../utils/copywriting');
const { requireLogin } = require('../../utils/auth-gate');
const { buildAppShare, enableWechatShareMenu } = require('../../utils/share');

const app = getApp();

Page({
  data: {
    isLogin: false,
    loginLoading: false,
    reviewLoginLoading: false,
    showReviewLogin: false,
    showReviewLoginPanel: false,
    reviewAccount: 'reviewer',
    reviewPassword: '',
    canProceedLogin: false,
    user: null,
    stats: {
      total_books: 0,
      total_pages: 0,
      total_entries: 0
    },
    goalProgress: {
      completed_books: 0,
      target_books: 1,
      book_percent: 0,
      active_days: 0,
      target_days: 20,
      day_percent: 0
    },
    editingNickname: false,
    nicknameDraft: '',
    savingNickname: false
  },

  onShow() {
    enableWechatShareMenu();
    this.setData({
      showReviewLogin: app.globalData.apiEnvVersion !== 'release'
    });
    this.initPage();
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({
        selected: 3,
        hasBook: !!app.globalData.currentBook,
        hasPartner: !!app.globalData.pair
      });
    }
  },

  noop() {},

  onLoginConsentChange(e) {
    const can = !!(e.detail && e.detail.canLogin);
    this.setData({ canProceedLogin: can });
  },

  onTapLoginBlocked() {
    wx.showToast({
      title: '请先完成上方隐私授权并勾选同意协议',
      icon: 'none'
    });
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
        },
        goalProgress: this.normalizeGoalProgress()
      });
      return;
    }

    await this.loadProfileData();
  },

  async loadProfileData() {
    try {
      const [profileRes, stats, goalRes] = await Promise.all([
        fetchProfileMe(),
        fetchProfileStats(),
        fetchReadingGoal()
      ]);
      const me = profileRes.user || null;
      const partner = profileRes.partner || null;
      app.syncReadingContext({
        user: me,
        pair: partner ? { partner } : null
      }, { persistUser: true });

      const userNickname = (me && me.nickname || '').trim();
      const partnerNickname = (partner && partner.nickname || '').trim();
      this.setData({
        isLogin: true,
        user: {
          ...me,
          partner
        },
        userInitial: userNickname ? userNickname.slice(0, 1) : '我',
        partnerInitial: partnerNickname ? partnerNickname.slice(0, 1) : '伴',
        stats,
        goalProgress: this.normalizeGoalProgress(goalRes.progress || {})
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
    if (!this.data.canProceedLogin) {
      this.onTapLoginBlocked();
      return;
    }
    if (this.data.loginLoading) {
      return;
    }
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

  onOpenReviewLogin() {
    if (!this.data.canProceedLogin) {
      this.onTapLoginBlocked();
      return;
    }
    this.setData({
      showReviewLoginPanel: true,
      reviewAccount: this.data.reviewAccount || 'reviewer',
      reviewPassword: ''
    });
  },

  onCloseReviewLogin() {
    this.setData({
      showReviewLoginPanel: false,
      reviewPassword: ''
    });
  },

  onReviewAccountInput(e) {
    this.setData({ reviewAccount: e.detail.value || '' });
  },

  onReviewPasswordInput(e) {
    this.setData({ reviewPassword: e.detail.value || '' });
  },

  async onSubmitReviewLogin() {
    if (this.data.reviewLoginLoading) {
      return;
    }
    const account = (this.data.reviewAccount || '').trim();
    const password = this.data.reviewPassword || '';
    if (!account || !password) {
      wx.showToast({ title: '请输入审核账号和密码', icon: 'none' });
      return;
    }

    this.setData({ reviewLoginLoading: true });
    try {
      await app.reviewLoginFlow(account, password);
      this.onCloseReviewLogin();
      await this.loadProfileData();
      wx.showToast({
        title: '登录成功',
        icon: 'success'
      });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '审核登录失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ reviewLoginLoading: false });
    }
  },

  normalizeGoalProgress(progress = {}) {
    const targetBooks = Math.max(Number(progress.target_books) || 1, 1);
    const targetDays = Math.max(Number(progress.target_days) || 1, 1);
    const completedBooks = Math.max(Number(progress.completed_books) || 0, 0);
    const activeDays = Math.max(Number(progress.active_days) || 0, 0);
    const bookPercent = Math.min(Math.round((completedBooks / targetBooks) * 100), 100);
    const dayPercent = Math.min(Math.round((activeDays / targetDays) * 100), 100);
    return {
      completed_books: completedBooks,
      target_books: targetBooks,
      book_percent: bookPercent,
      active_days: activeDays,
      target_days: targetDays,
      day_percent: dayPercent
    };
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
      const updatedUser = (payload && payload.user) || null;
      if (updatedUser) {
        app.syncUser(updatedUser, { persist: true });
        const newNickname = (updatedUser.nickname || '').trim();
        this.setData({
          user: {
            ...this.data.user,
            ...updatedUser
          },
          userInitial: newNickname ? newNickname.slice(0, 1) : '我',
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
          userInitial: '我',
          partnerInitial: '伴',
          editingNickname: false,
          nicknameDraft: '',
          stats: {
            total_books: 0,
            total_pages: 0,
            total_entries: 0
          },
          goalProgress: this.normalizeGoalProgress()
        });
        if (typeof this.getTabBar === 'function' && this.getTabBar()) {
          this.getTabBar().setData({
            selected: 3,
            hasBook: false,
            hasPartner: false
          });
        }
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

  onTapShareCircle() {
    wx.showToast({ title: '该功能暂不可用', icon: 'none' });
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
  },

  onShareAppMessage() {
    return buildAppShare({ title: '推荐一个阅读进度工具给你' });
  },

  onShareTimeline() {
    return { title: buildAppShare().title };
  }
});
