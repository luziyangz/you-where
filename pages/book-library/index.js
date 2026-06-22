const { createBook, fetchHome, requestBookSwitch, storeSearchBooks } = require('../../services/api');
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

const normalizeBook = (item = {}) => {
  const title = (item.title || '').trim() || '未命名书目';
  const author = (item.author || '').trim() || '作者未详';
  const totalPages = Number(item.total_pages || item.placeholder_pages || item.pages || 400) || 400;
  const intro = String(item.intro || item.top_review || item.description || '').trim();
  return {
    id: getCatalogId(item),
    title,
    author,
    total_pages: totalPages,
    cover_url: item.cover_url || '',
    cover_initial: title.slice(0, 1),
    desc: intro || '可加入你的阅读进度记录',
    tag: totalPages > 0 ? `${totalPages} 页` : '书籍资料'
  };
};

Page({
  data: {
    keyword: '',
    selectedCategory: 'all',
    categories: CATEGORIES,
    books: [],
    page: 1,
    hasMore: true,
    loading: false,
    addingId: ''
  },

  onShow() {
    enableWechatShareMenu();
    this.refreshReadingContext();
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({
        selected: 1,
        hasPartner: !!app.globalData.pair,
        hasBook: !!app.globalData.currentBook
      });
    }
    if (!this.data.books.length && !this.data.loading) {
      this.loadBooks(true);
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
      if (typeof this.getTabBar === 'function' && this.getTabBar()) {
        this.getTabBar().setData({
          selected: 1,
          hasPartner: !!app.globalData.pair,
          hasBook: !!app.globalData.currentBook
        });
      }
    } catch (error) {
      // 书库可继续浏览，加入记录时再给出明确提示。
    }
  },

  onPullDownRefresh() {
    Promise.resolve(this.loadBooks(true)).finally(() => wx.stopPullDownRefresh());
  },

  onReachBottom() {
    this.loadBooks(false);
  },

  onShareAppMessage() {
    return buildAppShare({ title: '一起挑一本书记录进度', path: '/pages/book-library/index' });
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
      const books = rows.map(normalizeBook).filter((item) => item.id);
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

  onManualAdd() {
    wx.switchTab({ url: '/pages/home/index' });
  },

  async onAddBook(e) {
    const id = e.currentTarget.dataset.id;
    const book = this.data.books.find((item) => item.id === id);
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
    if (!app.globalData.pair) {
      wx.showModal({
        title: '先建立共读关系',
        content: '这本书可以加入阅读记录。要同步给伙伴，需要先绑定一位共读伙伴。',
        cancelText: '继续浏览',
        confirmText: '去绑定',
        success: (res) => {
          if (res.confirm) {
            wx.navigateTo({ url: '/pages/partner/index' });
          }
        }
      });
      return;
    }

    const payload = {
      title: book.title,
      author: book.author === '作者未详' ? '' : book.author,
      total_pages: book.total_pages
    };
    const addRequest = app.globalData.currentBook ? requestBookSwitch(payload) : createBook(payload);
    this.setData({ addingId: id });
    try {
      const result = await addRequest;
      app.globalData.homeNeedsRefresh = true;
      wx.showToast({
        title: result && result.mode === 'switch_request' ? '已发起换书' : '已加入记录',
        icon: 'success'
      });
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
