const { createBook, fetchHome } = require('../../services/api');
const { COPY, formatApiError } = require('../../utils/copywriting');

const app = getApp();

Page({
  data: {
    isLogin: false,
    hasPartner: false,
    loginLoading: false,
    phoneLoginLoading: false,
    bookSubmitting: false,
    user: {
      nickname: '',
      avatar: '',
      join_code: ''
    },
    partner: {
      nickname: '',
      avatar: ''
    },
    currentBook: null,
    showBookPopup: false,
    bookForm: {
      title: '',
      author: '',
      total_pages: ''
    }
  },

  onShow() {
    this.initPage();
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({
        selected: 1
      });
    }
  },

  // 弹窗内容区域阻止事件冒泡（WXML 的 catchtap 需要绑定方法名）
  noop() {},

  async initPage() {
    const user = app.globalData.user;
    if (!user || !app.globalData.token) {
      this.setData({
        isLogin: false,
        hasPartner: false,
        user: {
          nickname: '',
          avatar: '',
          join_code: ''
        },
        partner: {
          nickname: '',
          avatar: ''
        },
        currentBook: null
      });
      app.syncReadingContext({
        pair: null,
        currentBook: null
      });
      return;
    }

    this.setData({
      isLogin: true,
      user
    });
    await this.loadHomeData();
  },

  async loadHomeData() {
    try {
      const data = await fetchHome();
      app.syncReadingContext({
        user: data.user,
        pair: data.pair,
        currentBook: data.current_book || null
      }, { persistUser: true });

      this.setData({
        isLogin: true,
        user: data.user,
        hasPartner: !!data.pair,
        partner: data.pair ? data.pair.partner : { nickname: '', avatar: '' },
        currentBook: data.current_book || null
      });

      if (typeof this.getTabBar === 'function' && this.getTabBar()) {
        this.getTabBar().setData({
          hasBook: !!data.current_book,
          hasPartner: !!data.pair
        });
      }
    } catch (error) {
      if (error.code === 401) {
        app.logout();
      }
      wx.showToast({
        title: formatApiError(error, '首页数据加载失败'),
        icon: 'none'
      });
    }
  },

  async onTapLogin() {
    this.setData({ loginLoading: true });
    try {
      await app.loginFlow();
      await this.loadHomeData();
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

  async onPhoneLogin(e) {
    const detail = e.detail || {};
    if (!detail.code && !detail.phoneNumber) {
      wx.showToast({ title: '需要授权手机号后继续', icon: 'none' });
      return;
    }

    this.setData({ phoneLoginLoading: true });
    try {
      await app.loginFlow({
        method: 'phone',
        phoneCode: detail.code,
        debugPhoneNumber: detail.phoneNumber
      });
      await this.loadHomeData();
      wx.showToast({
        title: '登录成功',
        icon: 'success'
      });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '手机号登录失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ phoneLoginLoading: false });
    }
  },

  onGoToPartner() {
    if (!this.data.isLogin) {
      wx.showToast({ title: COPY.common.loginRequired, icon: 'none' });
      return;
    }
    wx.switchTab({
      url: '/pages/partner/index'
    });
  },

  onTapAddBook() {
    if (!this.data.isLogin) {
      wx.showToast({ title: COPY.common.loginRequired, icon: 'none' });
      return;
    }
    if (!this.data.hasPartner) {
      wx.showToast({
        title: '请先绑定共读伙伴',
        icon: 'none'
      });
      return;
    }

    this.setData({
      showBookPopup: true
    });
  },

  onCloseBookPopup() {
    this.setData({
      showBookPopup: false,
      bookForm: {
        title: '',
        author: '',
        total_pages: ''
      }
    });
  },

  onBookFieldInput(e) {
    const { field } = e.currentTarget.dataset;
    this.setData({
      [`bookForm.${field}`]: e.detail.value
    });
  },

  async onSubmitBook() {
    const { title, author, total_pages } = this.data.bookForm;
    if (!title.trim()) {
      wx.showToast({
        title: '请填写书名',
        icon: 'none'
      });
      return;
    }

    const totalPagesInt = parseInt(total_pages, 10);
    if (!total_pages || isNaN(totalPagesInt) || totalPagesInt <= 0) {
      wx.showToast({
        title: '请填写正确的总页数',
        icon: 'none'
      });
      return;
    }

    this.setData({ bookSubmitting: true });
    try {
      await createBook({
        title: title.trim(),
        author: author.trim(),
        total_pages: totalPagesInt
      });
      this.onCloseBookPopup();
      await this.loadHomeData();
      wx.showToast({
        title: '书籍已添加',
        icon: 'success'
      });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '添加失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ bookSubmitting: false });
    }
  },

  onGotoProgress() {
    wx.navigateTo({
      url: '/pages/progress/index'
    });
  },

  onGoManagePartner() {
    this.onGoToPartner();
  },

  onCenterBtnClick() {
    if (!this.data.isLogin) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }
    if (!this.data.hasPartner) {
      this.onGoToPartner();
      return;
    }
    if (!this.data.currentBook) {
      this.onTapAddBook();
    } else {
      wx.navigateTo({
        url: '/pages/progress/index?open_composer=1'
      });
    }
  }
});

