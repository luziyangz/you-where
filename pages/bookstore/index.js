const { storeSearchBooks } = require('../../services/api');
const { formatApiError } = require('../../utils/copywriting');

const app = getApp();

Page({
  data: {
    keyword: '',
    loading: false,
    books: [],
    page: 1,
    hasMore: true
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({
        selected: 2
      });
    }
    // 进入书城默认加载热门公版书（不要求登录）
    this.setData({ books: [], page: 1, hasMore: true }, () => {
      this.loadPopular(true);
    });
  },

  onPullDownRefresh() {
    const keyword = (this.data.keyword || '').trim();
    const task = keyword ? this.searchBooks(true) : this.loadPopular(true);
    Promise.resolve(task).finally(() => {
      wx.stopPullDownRefresh();
    });
  },

  onReachBottom() {
    const keyword = (this.data.keyword || '').trim();
    if (keyword) {
      this.searchBooks(false);
      return;
    }
    this.loadPopular(false);
  },

  onKeywordInput(e) {
    this.setData({
      keyword: (e.detail.value || '').trim()
    });
  },

  onSearchConfirm() {
    this.searchBooks(true);
  },

  async loadPopular(reset = false) {
    if (!reset && !this.data.hasMore) {
      return;
    }
    const nextPage = reset ? 1 : Number(this.data.page || 1);
    this.setData({ loading: true });
    try {
      // query 为空时后端返回热门/最近缓存
      const payload = await storeSearchBooks('', nextPage);
      const newBooks = payload.books || [];
      const merged = reset ? newBooks : [...(this.data.books || []), ...newBooks];
      this.setData({
        books: merged,
        page: nextPage + 1,
        hasMore: newBooks.length >= 20
      });
      if (reset && Number(payload.network_synced_count || 0) > 0) {
        wx.showToast({
          title: `已从网络更新 ${payload.network_synced_count} 本`,
          icon: 'none'
        });
      }
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '加载书籍失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ loading: false });
    }
  },

  async searchBooks(reset = false) {
    const query = (this.data.keyword || '').trim();
    if (!query) {
      wx.showToast({ title: '请输入书名或作者', icon: 'none' });
      return;
    }

    if (!reset && !this.data.hasMore) {
      return;
    }

    const nextPage = reset ? 1 : Number(this.data.page || 1);
    this.setData({ loading: true });
    try {
      const payload = await storeSearchBooks(query, nextPage);
      const newBooks = payload.books || [];
      const merged = reset ? newBooks : [...(this.data.books || []), ...newBooks];
      this.setData({
        books: merged,
        page: nextPage + 1,
        hasMore: newBooks.length >= 20
      });
      if (reset && Number(payload.network_synced_count || 0) > 0) {
        wx.showToast({
          title: `已从网络更新 ${payload.network_synced_count} 本`,
          icon: 'none'
        });
      }
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '加载书籍失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ loading: false });
    }
  },

  onBookTap(e) {
    const catalogId = e.currentTarget.dataset.id || '';
    if (!catalogId) {
      return;
    }
    wx.navigateTo({
      url: `/pages/book-detail/index?catalog_id=${encodeURIComponent(catalogId)}`
    });
  }
});