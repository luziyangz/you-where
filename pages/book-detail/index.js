const { createBook, fetchHome, storeGetBook } = require('../../services/api');
const { formatApiError } = require('../../utils/copywriting');
const { requireLogin } = require('../../utils/auth-gate');

const app = getApp();

Page({
  data: {
    catalogId: '',
    loading: false,
    adding: false,
    book: null,
    hasPartner: false,
    hasCurrentBook: false
  },

  onLoad(query) {
    const catalogId = query && query.catalog_id ? decodeURIComponent(query.catalog_id) : '';
    this.setData({ catalogId });
  },

  onShow() {
    if (!requireLogin({ message: '请先登录后查看书籍详情' })) {
      return;
    }
    this.syncHomeContext();
    this.loadBook();
  },

  async syncHomeContext() {
    if (!app.globalData.token) {
      this.setData({
        hasPartner: false,
        hasCurrentBook: false
      });
      return null;
    }

    try {
      const payload = await fetchHome();
      app.syncReadingContext({
        user: payload.user,
        pair: payload.pair,
        currentBook: payload.current_book || null
      }, { persistUser: true });
      this.setData({
        hasPartner: !!payload.pair,
        hasCurrentBook: !!payload.current_book
      });
      return payload;
    } catch (error) {
      if (error.code === 401) {
        app.logout();
      }
      return null;
    }
  },

  async loadBook() {
    const catalogId = this.data.catalogId;
    if (!catalogId) {
      this.setData({ book: null });
      return;
    }

    this.setData({ loading: true });
    try {
      const payload = await storeGetBook(catalogId);
      this.setData({ book: payload.book || null });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '加载失败'),
        icon: 'none'
      });
      this.setData({ book: null });
    } finally {
      this.setData({ loading: false });
    }
  },

  onStartRead() {
    const catalogId = this.data.catalogId;
    if (!catalogId) {
      return;
    }
    wx.navigateTo({
      url: `/pages/reader/index?catalog_id=${encodeURIComponent(catalogId)}`
    });
  },

  async onAddToPair() {
    if (!app.globalData.token) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }
    await this.syncHomeContext();
    if (!this.data.hasPartner) {
      wx.showToast({ title: '请先去伙伴页绑定共读伙伴', icon: 'none' });
      wx.switchTab({
        url: '/pages/partner/index'
      });
      return;
    }
    if (this.data.hasCurrentBook) {
      wx.showToast({ title: '当前已有正在共读的书', icon: 'none' });
      wx.navigateTo({
        url: '/pages/progress/index'
      });
      return;
    }
    const catalogId = this.data.catalogId;
    if (!catalogId) {
      return;
    }

    this.setData({ adding: true });
    try {
      await createBook({ catalog_id: catalogId });
      await this.syncHomeContext();
      wx.showToast({ title: '已加入共读', icon: 'success' });
      wx.switchTab({
        url: '/pages/home/index'
      });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '加入失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ adding: false });
    }
  }
});

