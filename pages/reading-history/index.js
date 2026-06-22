const { fetchReadingHistory } = require('../../services/api');
const { formatApiError } = require('../../utils/copywriting');
const { requireLogin } = require('../../utils/auth-gate');

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
    if (!requireLogin({ message: '请先登录后查看历史' })) {
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
    this.loadHistory(false);
  },

  onGoBookstore() {
    wx.switchTab({
      url: '/pages/bookstore/index'
    });
  },

  // 从阅读历史进入书目：有书城 catalog 则详情页；否则若为当前共读则进进度 Tab
  onOpenHistoryBook(e) {
    const dataset = (e.currentTarget && e.currentTarget.dataset) || {};
    const catalogId = dataset.catalogId;
    const bookId = dataset.bookId;
    if (catalogId) {
      wx.navigateTo({
        url: `/pages/book-detail/index?catalog_id=${encodeURIComponent(String(catalogId))}`
      });
      return;
    }
    const cur = app.globalData.currentBook;
    if (bookId && cur && String(cur.book_id) === String(bookId)) {
      wx.switchTab({
        url: '/pages/progress/index'
      });
      return;
    }
    wx.showToast({
      title: '此书暂无书城详情，一般为手动添加',
      icon: 'none'
    });
  }
});
