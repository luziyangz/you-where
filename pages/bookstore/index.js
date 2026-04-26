const { storeSearchBooks } = require('../../services/api');
const { formatApiError } = require('../../utils/copywriting');
const { requireLogin } = require('../../utils/auth-gate');

const DEFAULT_CATEGORIES = [
  { key: 'all', name: '全部' },
  { key: 'foreign_classics', name: '国外名著' },
  { key: 'history', name: '历史' },
  { key: 'xin_xue', name: '心学' },
  { key: 'mysticism', name: '玄学术数' },
  { key: 'medicine', name: '中医经络' },
  { key: 'classics', name: '国学经典' }
];

Page({
  data: {
    keyword: '',
    selectedCategory: 'all',
    categories: DEFAULT_CATEGORIES,
    loading: false,
    books: [],
    page: 1,
    hasMore: true
  },

  onShow() {
    if (!requireLogin({ message: '请先登录后使用书城' })) {
      this.setData({ books: [], page: 1, hasMore: true, loading: false });
      return;
    }
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({
        selected: 2
      });
    }
    this.loadBooks(true);
  },

  onPullDownRefresh() {
    Promise.resolve(this.loadBooks(true)).finally(() => {
      wx.stopPullDownRefresh();
    });
  },

  onReachBottom() {
    this.loadBooks(false);
  },

  onKeywordInput(e) {
    this.setData({
      keyword: (e.detail.value || '').trim()
    });
  },

  onSearchConfirm() {
    this.loadBooks(true);
  },

  onCategoryTap(e) {
    const key = e.currentTarget.dataset.key || 'all';
    if (key === this.data.selectedCategory) {
      return;
    }
    this.setData({
      selectedCategory: key,
      books: [],
      page: 1,
      hasMore: true
    }, () => {
      this.loadBooks(true);
    });
  },

  async loadBooks(reset = false) {
    if (!reset && !this.data.hasMore) {
      return;
    }
    const nextPage = reset ? 1 : Number(this.data.page || 1);
    const query = (this.data.keyword || '').trim();
    const category = this.data.selectedCategory || 'all';

    this.setData({ loading: true });
    try {
      const payload = await storeSearchBooks(query, nextPage, category);
      const newBooks = payload.books || [];
      const merged = reset ? newBooks : [...(this.data.books || []), ...newBooks];
      this.setData({
        books: merged,
        categories: payload.categories && payload.categories.length ? payload.categories : DEFAULT_CATEGORIES,
        page: nextPage + 1,
        hasMore: Object.prototype.hasOwnProperty.call(payload, 'has_more') ? !!payload.has_more : newBooks.length >= 20
      });
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
