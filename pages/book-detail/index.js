const {
  createBook,
  fetchHome,
  requestBookSwitch,
  storeAddFavorite,
  storeGetBook,
  storeGetCatalogToc,
  storeRemoveFavorite
} = require('../../services/api');
const { formatApiError } = require('../../utils/copywriting');
const { requireLogin } = require('../../utils/auth-gate');
const { openExternalLink, copyExternalLink } = require('../../utils/open-link');
const { buildBookDetailShare, enableWechatShareMenu } = require('../../utils/share');
const { navigateTo: safeNavigateTo } = require('../../utils/safe-navigate');
const { buildReaderUrl } = require('../../utils/reading-progress-cache');

const app = getApp();

const normalizeBookFromDetail = (raw) => {
  if (!raw) {
    return null;
  }
  const book = { ...raw };
  if (typeof book.is_favorited !== 'boolean') {
    book.is_favorited = false;
  }
  book.pair_action = book.pair_action || (book.can_add_to_pair ? 'add' : 'none');
  book.pair_action_label = book.pair_action_label || '加入共读';
  book.pair_action_sub = book.pair_action_sub || '放进书桌';
  book.read_action = book.read_action || 'start';
  book.read_action_label = book.read_action_label || '开始阅读';
  book.read_action_sub = book.read_action_sub || '先翻几页';
  return book;
};

const normalizeBookFromCreate = (raw) => {
  if (!raw) {
    return null;
  }
  return {
    book_id: raw.book_id,
    catalog_id: raw.catalog_id || '',
    title: raw.title || '',
    author: raw.author || '',
    total_pages: Number(raw.total_pages || 0),
    status: raw.status || 'reading',
    my_progress: Number(raw.my_progress || 0),
    partner_progress: Number(raw.partner_progress || 0),
    reading_days: raw.reading_days,
    created_at: raw.created_at,
    finished_at: raw.finished_at
  };
};

Page({
  data: {
    catalogId: '',
    loading: false,
    loadError: false,
    adding: false,
    book: null,
    favoriting: false,
    hasPartner: false,
    hasCurrentBook: false,
    tocExpanded: false,
    tocLoading: false,
    tocLoaded: false,
    tocChapters: []
  },

  onShareAppMessage() {
    return buildBookDetailShare(this.data.book, this.data.catalogId);
  },

  onShareTimeline() {
    const payload = buildBookDetailShare(this.data.book, this.data.catalogId);
    return {
      title: payload.title,
      query: this.data.catalogId ? `catalog_id=${encodeURIComponent(this.data.catalogId)}` : ''
    };
  },

  onLoad(query) {
    const catalogId = query && query.catalog_id ? decodeURIComponent(query.catalog_id) : '';
    this.setData({ catalogId });
  },

  onShow() {
    enableWechatShareMenu();
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
      this.setData({ book: null, loadError: false });
      return;
    }
    if (this._loadingBook) {
      return;
    }
    this._loadingBook = true;

    this.setData({ loading: true, loadError: false });
    try {
      const payload = await storeGetBook(catalogId);
      const book = normalizeBookFromDetail(payload.book ? { ...payload.book } : null);
      this.setData({
        book,
        loadError: false,
        tocExpanded: false,
        tocLoaded: false,
        tocChapters: []
      });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '加载失败'),
        icon: 'none'
      });
      this.setData({ book: null, loadError: true });
    } finally {
      this._loadingBook = false;
      this.setData({ loading: false });
    }
  },

  onRetryLoadBook() {
    this.loadBook();
  },

  onTapToggleToc() {
    const book = this.data.book;
    if (!book || book.reader_mode !== 'pager') {
      return;
    }
    const next = !this.data.tocExpanded;
    this.setData({ tocExpanded: next });
    if (next && !this.data.tocLoaded && !this.data.tocLoading) {
      this.loadToc();
    }
  },

  async loadToc() {
    const cid = this.data.catalogId;
    if (!cid) {
      return;
    }
    this.setData({ tocLoading: true });
    try {
      const data = await storeGetCatalogToc(cid);
      const raw = data.chapters || [];
      const tocChapters = raw.map((c, i) => ({
        title: c.title,
        page: c.page,
        tocKey: `toc-${i}-${c.page}`
      }));
      this.setData({
        tocChapters,
        tocLoaded: true
      });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '目录加载失败'),
        icon: 'none'
      });
      this.setData({ tocChapters: [] });
    } finally {
      this.setData({ tocLoading: false });
    }
  },

  onTapTocChapter(e) {
    const page = Number(e.currentTarget.dataset.page || 1);
    const catalogId = this.data.catalogId;
    if (!catalogId || !page) {
      return;
    }
    safeNavigateTo(buildReaderUrl(catalogId, { page, jump: true }), this);
  },

  async onToggleFavorite() {
    const book = this.data.book;
    const catalogId = this.data.catalogId;
    if (!book || !catalogId || this.data.favoriting) {
      return;
    }
    this.setData({ favoriting: true });
    try {
      if (book.is_favorited) {
        await storeRemoveFavorite(catalogId);
        this.setData({ 'book.is_favorited': false });
        wx.showToast({ title: '已取消收藏', icon: 'none' });
      } else {
        await storeAddFavorite(catalogId);
        this.setData({ 'book.is_favorited': true });
        wx.showToast({ title: '已收藏', icon: 'success' });
      }
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '操作失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ favoriting: false });
    }
  },

  onContinueReading() {
    const book = this.data.book;
    const catalogId = this.data.catalogId;
    if (!book || book.reader_mode !== 'pager' || !catalogId) {
      return;
    }
    safeNavigateTo(
      buildReaderUrl(catalogId, { page: book.reading_progress_page || 0 }),
      this
    );
  },

  onStartRead() {
    const book = this.data.book;
    const catalogId = this.data.catalogId;
    if (!catalogId || !book || book.reader_mode !== 'pager') {
      return;
    }
    if (book.read_action === 'reread') {
      safeNavigateTo(buildReaderUrl(catalogId, { restart: true }), this);
      return;
    }
    safeNavigateTo(
      buildReaderUrl(catalogId, { page: book.reading_progress_page || 0 }),
      this
    );
  },

  onOpenExternalRead() {
    const url = this.data.book && this.data.book.external_read_url;
    if (!url) {
      wx.showToast({ title: '无可打开链接', icon: 'none' });
      return;
    }
    openExternalLink(url, {
      title: (this.data.book && this.data.book.title) || '阅读链接',
      modalContent: '该阅读链接暂未接入小程序内浏览，可复制后在浏览器打开。'
    });
  },

  onCopyExternalRead() {
    const url = this.data.book && this.data.book.external_read_url;
    if (!url) {
      wx.showToast({ title: '无可复制链接', icon: 'none' });
      return;
    }
    copyExternalLink(url, '链接已复制');
  },

  onOpenDetailLink() {
    const url = this.data.book && this.data.book.detail_url;
    if (!url) {
      return;
    }
    openExternalLink(url, {
      title: '书籍参考',
      modalContent: '该参考链接需在浏览器中查看，是否复制？'
    });
  },

  onTapShareBook() {
    enableWechatShareMenu();
  },

  onPairAction() {
    const book = this.data.book;
    if (!book || !book.can_add_to_pair) {
      return;
    }
    const action = book.pair_action || 'add';
    if (action === 'view') {
      wx.switchTab({ url: '/pages/progress/index' });
      return;
    }
    if (action === 'in_catalog') {
      wx.switchTab({ url: '/pages/progress/index' });
      return;
    }
    if (action === 'rejoin') {
      wx.showModal({
        title: '重新共读',
        content: '将向伙伴申请再次共读此书，对方同意后开始新的共读记录。',
        confirmText: '发送申请',
        success: (res) => {
          if (res.confirm) {
            this.submitAddToPair();
          }
        }
      });
      return;
    }
    if (action === 'switch_review') {
      wx.switchTab({ url: '/pages/home/index' });
      return;
    }
    if (action === 'switch_pending') {
      wx.showToast({ title: '等待伙伴同意', icon: 'none' });
      return;
    }
    if (action === 'switch') {
      wx.showModal({
        title: '申请换书',
        content: '换书需共读伙伴同意，确认向伙伴发起申请吗？',
        confirmText: '申请',
        success: (res) => {
          if (res.confirm) {
            this.submitSwitchRequest();
          }
        }
      });
      return;
    }
    this.submitAddToPair(false);
  },

  async submitSwitchRequest() {
    const catalogId = this.data.catalogId;
    if (!catalogId) {
      return;
    }
    this.setData({ adding: true });
    try {
      const result = await requestBookSwitch({ catalog_id: catalogId });
      const bookPayload = (result && result.mode === 'book' && result.book) || null;
      const currentBook = normalizeBookFromCreate(bookPayload);
      app.globalData.homeNeedsRefresh = true;
      await this.syncHomeContext();
      if (currentBook) {
        app.syncCurrentBook(currentBook);
      }
      await this.loadBook();
      wx.showToast({
        title: currentBook ? '已切换' : '已申请',
        icon: 'success'
      });
      wx.switchTab({ url: '/pages/home/index' });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '申请失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ adding: false });
    }
  },

  async submitAddToPair() {
    if (!app.globalData.token) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }
    await this.syncHomeContext();
    if (!this.data.hasPartner) {
      wx.showToast({ title: '请先去伙伴页绑定共读伙伴', icon: 'none' });
      wx.navigateTo({ url: '/pages/partner/index' });
      return;
    }

    const catalogId = this.data.catalogId;
    if (!catalogId) {
      return;
    }

    this.setData({ adding: true });
    try {
      const created = await createBook({ catalog_id: catalogId });
      if (created && created.mode === 'switch_request') {
        app.globalData.homeNeedsRefresh = true;
        await this.syncHomeContext();
        await this.loadBook();
        wx.showToast({ title: '已申请，等待伙伴同意', icon: 'none' });
        wx.switchTab({ url: '/pages/home/index' });
        return;
      }
      const bookPayload = (created && created.mode === 'book' && created.book) || created;
      const currentBook = normalizeBookFromCreate(bookPayload && bookPayload.book_id ? bookPayload : null);
      app.globalData.homeNeedsRefresh = true;
      await this.syncHomeContext();
      if (currentBook) {
        app.syncCurrentBook(currentBook);
      }
      await this.loadBook();

      const action = this.data.book && this.data.book.pair_action;
      if (action === 'view') {
        wx.showToast({ title: '已在共读', icon: 'none' });
        wx.switchTab({ url: '/pages/progress/index' });
        return;
      }

      wx.showToast({ title: '已加入', icon: 'success' });
      wx.switchTab({ url: '/pages/home/index' });
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
