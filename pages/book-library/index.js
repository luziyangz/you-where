const { createBook, fetchBooks, fetchHome, storeSearchBooks } = require('../../services/api');
const { formatApiError } = require('../../utils/copywriting');
const { enableWechatShareMenu, buildAppShare } = require('../../utils/share');

const app = getApp();

const CATEGORIES = [
  { key: 'all', name: '全部' },
  { key: 'literature', name: '文学' },
  { key: 'history', name: '历史' },
  { key: 'poetry', name: '诗词' },
  { key: 'classical', name: '经典' },
  { key: 'philosophy', name: '思想' },
  { key: 'medicine', name: '健康' }
];

const getCatalogId = (item) => item && (item.catalogId || item['catalog' + '_id'] || '');

const normalizeLibraryBook = (item = {}) => {
  const title = (item.title || '').trim() || '未命名书目';
  const author = (item.author || '').trim() || '作者未详';
  const totalPages = Number(item.total_pages || item.placeholder_pages || item.pages || 400) || 400;
  const rating = Number(item.review_rating || item.douban_rating || 0);
  const summary = String(item.top_review || item.intro || item.description || '').trim();
  const recommendText = rating > 0 ? `推荐值 ${Math.round((rating <= 10 ? rating * 10 : rating) * 10) / 10}%` : '';
  return {
    id: getCatalogId(item),
    title,
    author,
    total_pages: totalPages,
    cover_url: item.cover_url || '',
    cover_initial: title.slice(0, 1),
    meta: `${author} · ${totalPages} 页`,
    recommend_text: recommendText,
    reason: summary || '适合加入阅读进度记录',
    action_label: '加入记录'
  };
};

const normalizeRecordBook = (item = {}) => {
  const title = (item.title || '').trim() || '未命名书目';
  const author = (item.author || '').trim() || '作者未详';
  const totalPages = Number(item.total_pages || 0);
  const progress = Number(item.my_progress || 0);
  const percent = totalPages > 0 ? Math.min(Math.round((progress / totalPages) * 100), 100) : 0;
  return {
    id: item.book_id || `${title}-${author}`,
    title,
    author,
    total_pages: totalPages,
    cover_url: item.cover_url || '',
    cover_initial: title.slice(0, 1),
    meta: `${author} · ${progress}/${totalPages || '--'} 页`,
    reason: item.display_label || '正在记录',
    percent,
    action_label: '看进度'
  };
};

Page({
  data: {
    shelfTab: 'browse',
    keyword: '',
    selectedCategory: 'all',
    categories: CATEGORIES,
    books: [],
    records: [],
    page: 1,
    hasMore: true,
    loading: false,
    recordLoading: false,
    addingId: '',
    activeBook: null,
    showDetail: false
  },

  onShow() {
    enableWechatShareMenu();
    this.refreshReadingContext();
    this.updateTabBar();
    if (this.data.shelfTab === 'records') {
      this.loadRecords();
    } else if (!this.data.books.length && !this.data.loading) {
      this.loadBooks(true);
    }
  },

  updateTabBar() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({
        selected: 1,
        hasPartner: !!app.globalData.pair,
        hasBook: !!app.globalData.currentBook
      });
    }
  },

  async refreshReadingContext() {
    if (!app.globalData.token || !app.globalData.user) {
      return;
    }
    try {
      const data = await fetchHome();
      app.syncReadingContext({
        user: data.user || app.globalData.user,
        pair: data.pair || null,
        currentBook: data.current_book || null
      }, { persistUser: true });
      this.updateTabBar();
    } catch (error) {
      // 书库可继续浏览，加入记录时再给出明确提示。
    }
  },

  onPullDownRefresh() {
    const task = this.data.shelfTab === 'records' ? this.loadRecords() : this.loadBooks(true);
    Promise.resolve(task).finally(() => wx.stopPullDownRefresh());
  },

  onReachBottom() {
    if (this.data.shelfTab === 'browse') {
      this.loadBooks(false);
    }
  },

  onShareAppMessage() {
    return buildAppShare({ title: '一起挑一本书记录进度', path: '/pages/book-library/index' });
  },

  onShelfTabTap(e) {
    const tab = e.currentTarget.dataset.tab || 'browse';
    if (tab === this.data.shelfTab) {
      return;
    }
    this.setData({ shelfTab: tab }, () => {
      if (tab === 'records') {
        this.loadRecords();
      } else if (!this.data.books.length) {
        this.loadBooks(true);
      }
    });
  },

  onKeywordInput(e) {
    const keyword = e.detail.value || '';
    this.setData({ keyword });
    clearTimeout(this.searchTimer);
    this.searchTimer = setTimeout(() => {
      this.setData({ page: 1, books: [], hasMore: true }, () => this.loadBooks(true));
    }, 300);
  },

  onSearchConfirm() {
    this.setData({ page: 1, books: [], hasMore: true }, () => this.loadBooks(true));
  },

  onCategoryTap(e) {
    const key = e.currentTarget.dataset.key || 'all';
    if (key === this.data.selectedCategory) {
      return;
    }
    this.setData({
      selectedCategory: key,
      page: 1,
      books: [],
      hasMore: true
    }, () => this.loadBooks(true));
  },

  async loadBooks(reset = false) {
    if (this.data.loading || (!reset && !this.data.hasMore)) {
      return;
    }
    const nextPage = reset ? 1 : this.data.page;
    this.setData({ loading: true });
    try {
      const payload = await storeSearchBooks((this.data.keyword || '').trim(), nextPage, this.data.selectedCategory);
      const rows = Array.isArray(payload.books) ? payload.books : [];
      const books = rows.map(normalizeLibraryBook).filter((item) => item.id);
      this.setData({
        books: reset ? books : this.data.books.concat(books),
        page: nextPage + 1,
        hasMore: !!payload.has_more
      });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '加载书库失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ loading: false });
    }
  },

  async loadRecords() {
    if (!app.globalData.token || !app.globalData.user) {
      this.setData({ records: [] });
      return;
    }
    this.setData({ recordLoading: true });
    try {
      const payload = await fetchBooks();
      const records = Array.isArray(payload.books) ? payload.books.map(normalizeRecordBook) : [];
      this.setData({ records });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '加载记录失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ recordLoading: false });
    }
  },

  onManualAdd() {
    wx.switchTab({ url: '/pages/home/index' });
  },

  onBookTap(e) {
    const id = e.currentTarget.dataset.id;
    const book = this.data.books.find((item) => item.id === id);
    if (!book) {
      return;
    }
    this.setData({
      activeBook: book,
      showDetail: true
    });
  },

  onCloseDetail() {
    this.setData({
      showDetail: false,
      activeBook: null
    });
  },

  onOpenRecord(e) {
    const id = e.currentTarget.dataset.id;
    const record = this.data.records.find((item) => item.id === id);
    if (!record) {
      return;
    }
    if (app.globalData.currentBook && String(app.globalData.currentBook.book_id) === String(id)) {
      wx.switchTab({ url: '/pages/progress/index' });
      return;
    }
    wx.showToast({ title: '历史记录可在历史页查看', icon: 'none' });
  },

  onAddBook(e) {
    const id = (e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.id) || (this.data.activeBook && this.data.activeBook.id);
    const book = this.data.books.find((item) => item.id === id) || this.data.activeBook;
    return this.addBookToRecord(book);
  },

  async addBookToRecord(book) {
    if (!book) {
      return;
    }
    await this.refreshReadingContext();
    if (!app.globalData.token || !app.globalData.user) {
      wx.showModal({
        title: '登录后保存',
        content: '你可以先浏览书库。要把这本书加入阅读记录，需要先登录。',
        cancelText: '继续浏览',
        confirmText: '去登录',
        success: (res) => {
          if (res.confirm) {
            wx.switchTab({ url: '/pages/profile/index' });
          }
        }
      });
      return;
    }
    const payload = {
      title: book.title,
      author: book.author === '作者未详' ? '' : book.author,
      total_pages: book.total_pages,
      replace_current: !!app.globalData.currentBook
    };
    const addRequest = createBook(payload);
    this.setData({ addingId: book.id });
    try {
      const result = await addRequest;
      app.globalData.homeNeedsRefresh = true;
      this.onCloseDetail();
      wx.showToast({
        title: result && result.mode === 'switch_request' ? '已发起换书' : '已加入记录',
        icon: 'success'
      });
      this.refreshReadingContext();
      if (this.data.shelfTab === 'records') {
        this.loadRecords();
      }
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '加入失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ addingId: '' });
    }
  }
});
