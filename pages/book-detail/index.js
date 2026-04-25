const { createBook, storeGetBook } = require('../../services/api');
const { formatApiError } = require('../../utils/copywriting');

const app = getApp();

Page({
  data: {
    catalogId: '',
    loading: false,
    adding: false,
    book: null
  },

  onLoad(query) {
    const catalogId = query && query.catalog_id ? decodeURIComponent(query.catalog_id) : '';
    this.setData({ catalogId });
  },

  onShow() {
    this.loadBook();
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
    const catalogId = this.data.catalogId;
    if (!catalogId) {
      return;
    }

    this.setData({ adding: true });
    try {
      await createBook({ catalog_id: catalogId });
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

