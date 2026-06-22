const { fetchReadingHistory } = require('../../services/api');
const { formatApiError } = require('../../utils/copywriting');

const app = getApp();

Page({
  data: {
    loading: false,
    items: [],
    page: 1,
    pageSize: 10,
    hasMore: true
  },

  onShow() {
    if (!app.globalData.token || !app.globalData.user) {
      this.setData({
        loading: false,
        items: [],
        page: 1,
        hasMore: false
      });
      return;
    }
    this.loadHistory(true);
  },

  async loadHistory(reset = false) {
    if (!reset && !this.data.hasMore) {
      return;
    }
    const nextPage = reset ? 1 : this.data.page;
    this.setData({ loading: true });
    try {
      const payload = await fetchReadingHistory(nextPage, this.data.pageSize);
      const rows = payload.items || [];
      this.setData({
        items: reset ? rows : [...this.data.items, ...rows],
        page: nextPage + 1,
        hasMore: !!payload.has_more
      });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '加载历史失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ loading: false });
    }
  },

  onReachBottom() {
    if (!app.globalData.token || !app.globalData.user) {
      return;
    }
    this.loadHistory(false);
  },

  onGoHomeAddBook() {
    wx.switchTab({
      url: '/pages/home/index'
    });
  },

  onOpenHistoryBook(e) {
    const dataset = (e.currentTarget && e.currentTarget.dataset) || {};
    const bookId = dataset.bookId;
    const cur = app.globalData.currentBook;
    if (bookId && cur && String(cur.book_id) === String(bookId)) {
      wx.switchTab({
        url: '/pages/progress/index'
      });
      return;
    }
    wx.showToast({
      title: '历史记录仅用于回顾进度',
      icon: 'none'
    });
  }
});
