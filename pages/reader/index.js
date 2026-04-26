const { createEntry, fetchHome, storeReadPage } = require('../../services/api');
const { formatApiError } = require('../../utils/copywriting');
const { requireLogin } = require('../../utils/auth-gate');

const app = getApp();

Page({
  data: {
    catalogId: '',
    loading: false,
    syncing: false,
    page: 1,
    pageData: null
  },

  onLoad(query) {
    const catalogId = query && query.catalog_id ? decodeURIComponent(query.catalog_id) : '';
    const page = query && query.page ? Number(query.page) : 1;
    this.setData({
      catalogId,
      page: Number.isFinite(page) && page > 0 ? page : 1
    });
  },

  onShow() {
    if (!requireLogin({ message: '请先登录后阅读' })) {
      return;
    }
    this.loadPage();
  },

  async syncHomeContext() {
    if (!app.globalData.token) {
      return null;
    }

    try {
      const payload = await fetchHome();
      app.syncReadingContext({
        user: payload.user,
        pair: payload.pair,
        currentBook: payload.current_book || null
      }, { persistUser: true });
      return payload;
    } catch (error) {
      if (error.code === 401) {
        app.logout();
      }
      throw error;
    }
  },

  async loadPage() {
    const catalogId = this.data.catalogId;
    if (!catalogId) {
      this.setData({ pageData: null });
      return;
    }

    this.setData({ loading: true });
    try {
      const payload = await storeReadPage(catalogId, this.data.page);
      this.setData({ pageData: payload });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '加载失败'),
        icon: 'none'
      });
      this.setData({ pageData: null });
    } finally {
      this.setData({ loading: false });
    }
  },

  onPrev() {
    const pageData = this.data.pageData;
    if (!pageData || pageData.page <= 1) {
      return;
    }
    this.setData({ page: pageData.page - 1 }, () => this.loadPage());
  },

  onNext() {
    const pageData = this.data.pageData;
    if (!pageData || pageData.page >= pageData.total_pages) {
      return;
    }
    this.setData({ page: pageData.page + 1 }, () => this.loadPage());
  },

  async onSyncProgress() {
    if (!app.globalData.token) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }

    this.setData({ syncing: true });
    try {
      // 仅当已经存在“正在共读的书”时才同步进度。
      // 用户可能只是预览阅读（尚未加入共读），此时给出提示。
      const homeData = await this.syncHomeContext();
      const book = homeData && homeData.current_book ? homeData.current_book : null;
      if (!book) {
        wx.showToast({ title: '请先在书籍详情页「加入共读」', icon: 'none' });
        return;
      }

      await createEntry({
        book_id: book.book_id,
        page: Number(this.data.pageData && this.data.pageData.page) || 1,
        note_content: ''
      });
      const latestHomeData = await this.syncHomeContext();
      if (latestHomeData && latestHomeData.current_book) {
        app.syncCurrentBook(latestHomeData.current_book);
      }
      wx.showToast({ title: '进度已同步', icon: 'success' });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '同步失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ syncing: false });
    }
  }
});

