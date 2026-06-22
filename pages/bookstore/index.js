const { storeGetMyShelf, storeImportReadUrl, storeSearchBooks, storeUploadTxtBook } = require('../../services/api');
const { formatApiError } = require('../../utils/copywriting');
const { requireLogin } = require('../../utils/auth-gate');
const { buildBookstoreShare, enableWechatShareMenu } = require('../../utils/share');
const {
  openTxtFromChatPicker,
  showChooseTxtHelpModal
} = require('../../utils/choose-txt-from-chat');
const { navigateToPrivacyAuthorize, consumePrivacyResume } = require('../../utils/privacy-before-action');

/** 与后端 STORE_CATEGORIES 一致；接口失败时作兜底 */
const DEFAULT_CATEGORIES = [
  { key: 'all', name: '全部' },
  { key: 'fiction', name: '精品小说' },
  { key: 'classical', name: '古典文学' },
  { key: 'poetry', name: '古代诗词' },
  { key: 'world_fiction', name: '世界名著' },
  { key: 'literature', name: '文学' },
  { key: 'history', name: '历史' },
  { key: 'philosophy', name: '哲学宗教' },
  { key: 'medicine', name: '医学健康' }
];

/** 统一为微信读书式列表展示字段 */
const normalizeStoreBook = (item) => {
  if (!item || !item.catalog_id) {
    return item;
  }
  const title = (item.title || '').trim() || '未命名书目';
  const author = (item.author || '').trim() || '作者未详';
  const rawRating = parseFloat(item.review_rating || item.douban_rating);
  let recommendText = '';
  if (!Number.isNaN(rawRating) && rawRating > 0) {
    const pct = rawRating <= 10 ? Math.round(rawRating * 10 * 10) / 10 : Math.round(rawRating * 10) / 10;
    recommendText = `推荐值 ${pct}%`;
  }
  let reason = String(item.top_review || item.intro || '').trim();
  reason = reason.replace(/^\d+(?:\.\d+)?分\s*·\s*/, '');
  if (!reason) {
    reason = item.has_local_text ? '支持站内分页阅读与共读' : '适合建立共读进度记录';
  }
  let readTag = '';
  if (item.reading_progress_page) {
    readTag = `已读至第 ${item.reading_progress_page} 页`;
  } else if (item.has_local_text) {
    readTag = '可站内阅读';
  } else if (item.has_text) {
    readTag = '可全文阅读';
  } else {
    readTag = '共读推荐';
  }
  return {
    ...item,
    title,
    author_line: author,
    cover_initial: title.slice(0, 1),
    recommend_text: recommendText,
    reason_line: reason,
    read_tag: readTag
  };
};

const normalizeStoreBooks = (list) => (Array.isArray(list) ? list.map(normalizeStoreBook) : []);

const logTxtImportDebug = (...args) => {
  try {
    console.log('[txt-import]', ...args);
  } catch (e) {
    // ignore
  }
};

Page({
  data: {
    /** browse：分类浏览；favorites / recent：个人书架 */
    shelfTab: 'browse',
    keyword: '',
    selectedCategory: 'all',
    categories: DEFAULT_CATEGORIES,
    loading: false,
    books: [],
    page: 1,
    hasMore: true,
    showUrlPopup: false,
    urlSubmitting: false,
    urlForm: {
      title: '',
      author: '',
      read_url: '',
      estimated_pages: '400'
    },
    showTxtPopup: false,
    txtSubmitting: false,
    txtFilePath: '',
    txtFileName: '',
    txtPickerBusy: false,
    txtPrivacyReadyHint: false,
    supportTxtAgreeBtn: true,
    txtNeedsPrivacyAuthorization: false,
    txtForm: {
      title: '',
      author: ''
    },
    storeHint: ''
  },

  noop() {},

  onLoad() {
    this.refreshTxtAgreeSupport();
  },

  refreshTxtAgreeSupport() {
    const supportTxtAgreeBtn =
      typeof wx.canIUse === 'function'
        ? wx.canIUse('button.open-type.agreePrivacyAuthorization')
        : typeof wx.chooseMessageFile === 'function';
    const patch = { supportTxtAgreeBtn };
    logTxtImportDebug('refresh support', {
      supportTxtAgreeBtn,
      hasGetPrivacySetting: typeof wx.getPrivacySetting === 'function',
      hasChooseMessageFile: typeof wx.chooseMessageFile === 'function'
    });
    if (typeof wx.getPrivacySetting !== 'function') {
      patch.txtNeedsPrivacyAuthorization = false;
      this.setData(patch);
      return;
    }
    wx.getPrivacySetting({
      success: (res) => {
        logTxtImportDebug('getPrivacySetting success', res);
        this.setData({
          ...patch,
          txtNeedsPrivacyAuthorization: !!(res && res.needAuthorization)
        });
      },
      fail: (err) => {
        logTxtImportDebug('getPrivacySetting fail', err);
        this.setData({
          ...patch,
          txtNeedsPrivacyAuthorization: false
        });
      }
    });
  },

  onShow() {
    enableWechatShareMenu();
    this.refreshTxtAgreeSupport();
    // 从微信选文件界面返回时勿清掉进行中状态，否则 success 回调可能异常
    if (!this._txtPickerRunning) {
      if (this._txtPickerWatchdog) {
        clearTimeout(this._txtPickerWatchdog);
        this._txtPickerWatchdog = null;
      }
      if (this.data.txtPickerBusy) {
        this.setData({ txtPickerBusy: false });
      }
    }
    const shouldResumeTxtImport = consumePrivacyResume('txt_import');
    if (!requireLogin({ message: '请先登录后使用书城' })) {
      this.setData({ books: [], page: 1, hasMore: true, loading: false });
      return;
    }
    if (shouldResumeTxtImport) {
      this.setData({ txtPrivacyReadyHint: true });
    }
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({
        selected: 1
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

  onShareAppMessage() {
    return buildBookstoreShare();
  },

  onShareTimeline() {
    return { title: buildBookstoreShare().title };
  },

  onShelfTabTap(e) {
    const tab = e.currentTarget.dataset.tab || 'browse';
    if (tab === this.data.shelfTab) {
      return;
    }
    this.setData({
      shelfTab: tab,
      books: [],
      page: 1,
      hasMore: true,
      storeHint: ''
    }, () => this.loadBooks(true));
  },

  onKeywordInput(e) {
    if (this.data.shelfTab !== 'browse') {
      return;
    }
    const keyword = e.detail.value || '';
    this.setData({ keyword });
    if (this._searchDebounceTimer) {
      clearTimeout(this._searchDebounceTimer);
    }
    const runSearch = () => {
      const q = (this.data.keyword || '').trim();
      this.setData({ keyword: q, books: [], page: 1, hasMore: true }, () => this.loadBooks(true));
    };
    if (!(keyword || '').trim()) {
      runSearch();
      return;
    }
    this._searchDebounceTimer = setTimeout(runSearch, 420);
  },

  onSearchConfirm() {
    if (this.data.shelfTab !== 'browse') {
      return;
    }
    if (this._searchDebounceTimer) {
      clearTimeout(this._searchDebounceTimer);
      this._searchDebounceTimer = null;
    }
    const q = (this.data.keyword || '').trim();
    this.setData({ keyword: q, books: [], page: 1, hasMore: true }, () => this.loadBooks(true));
  },

  onCategoryTap(e) {
    if (this.data.shelfTab !== 'browse') {
      return;
    }
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
    if (!reset && (!this.data.hasMore || this._loadingMore)) {
      return;
    }
    this._loadingMore = true;
    const nextPage = reset ? 1 : Number(this.data.page || 1);
    const query = (this.data.keyword || '').trim();
    const category = this.data.selectedCategory || 'all';
    const shelfTab = this.data.shelfTab || 'browse';

    this.setData({ loading: true });
    try {
      let payload;
      if (shelfTab === 'browse') {
        payload = await storeSearchBooks(query, nextPage, category);
      } else {
        payload = await storeGetMyShelf(shelfTab, nextPage);
      }
      const newBooks = normalizeStoreBooks(payload.books || []);
      const prev = reset ? [] : (this.data.books || []);
      const seen = new Set(prev.map((b) => b.catalog_id));
      const uniqueNew = newBooks.filter((b) => b.catalog_id && !seen.has(b.catalog_id));
      const merged = reset ? newBooks : [...prev, ...uniqueNew];
      const apiHasMore = Object.prototype.hasOwnProperty.call(payload, 'has_more') ? !!payload.has_more : newBooks.length >= 20;
      const patch = {
        books: merged,
        page: nextPage + 1,
        hasMore: apiHasMore && (reset || uniqueNew.length > 0)
      };
      if (shelfTab === 'browse') {
        patch.categories = payload.categories && payload.categories.length ? payload.categories : DEFAULT_CATEGORIES;
        const fulltextCount = merged.filter((b) => b.has_local_text).length;
        patch.storeHint = payload.network_error
          ? '外网书库同步失败，以下为站内已入库书目（不含本次网络目录更新）'
          : payload.network_skipped
            ? fulltextCount > 0
              ? `站内公版全书 ${fulltextCount} 本可直接阅读；其余为共读推荐（可导入 TXT）`
              : '公版全书正在入库，请稍后下拉刷新；也可先导入 TXT 共读'
            : '';
      } else {
        patch.storeHint = '';
      }
      this.setData(patch);
    } catch (error) {
      this.setData({ storeHint: '' });
      wx.showToast({
        title: formatApiError(error, '加载书籍失败'),
        icon: 'none'
      });
    } finally {
      this._loadingMore = false;
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
  },

  /** 应用选中的聊天 TXT 到导入弹层 */
  applyChosenTxtFile(file, savedForm = {}) {
    const guessTitle = (file.guessTitle || '').trim();
    const title = (savedForm.title || '').trim() || guessTitle || 'import';
    this.setData({
      showTxtPopup: true,
      txtSubmitting: false,
      txtFilePath: file.path,
      txtFileName: file.name,
      txtForm: {
        title,
        author: (savedForm.author || '').trim()
      }
    });
    wx.showToast({ title: '已选择文件', icon: 'success' });
    wx.showModal({
      title: '确认导入 TXT',
      content: `已选择「${file.name || 'TXT 文件'}」，是否现在导入？`,
      confirmText: '导入',
      cancelText: '稍后',
      success: (res) => {
        if (res.confirm) {
          this.onSubmitTxtImport();
        }
      }
    });
  },

  finishTxtPickerUi() {
    if (this._txtPickerWatchdog) {
      clearTimeout(this._txtPickerWatchdog);
      this._txtPickerWatchdog = null;
    }
    if (typeof wx.hideLoading === 'function') {
      wx.hideLoading();
    }
    this._txtPickerRunning = false;
    this.setData({ txtPickerBusy: false });
  },

  clearTxtPrivacyResume() {
    const app = getApp();
    if (app && app.globalData && app.globalData.__privacyResumeAction === 'txt_import') {
      app.globalData.__privacyResumeAction = '';
    }
  },

  handleTxtPickFail(err) {
    const code = err && err.code;
    if (code === 'cancel') {
      if (!this.data.txtFilePath) {
        this.setData({ showTxtPopup: false });
      }
      return;
    }
    if (code === 'unsupported') {
      wx.showModal({
        title: '无法从聊天选文件',
        content: '请升级微信后重试，或使用「导入网页 / TXT 链接」。',
        confirmText: '用链接导入',
        cancelText: '知道了',
        success: (res) => {
          if (res.confirm) {
            this.onCloseTxtPopup();
            this.onOpenUrlPopup();
          }
        }
      });
      return;
    }
    if (code === 'privacy') {
      const app = getApp();
      if (app && typeof app.globalData.__privacyAuthResolve === 'function') {
        wx.showToast({ title: '请先在隐私页点击「同意并继续」', icon: 'none', duration: 2800 });
        return;
      }
      navigateToPrivacyAuthorize('txt_import');
      return;
    }
    if (code === 'privacy_scope_missing') {
      wx.showModal({
        title: '暂不能选择聊天文件',
        content: '小程序后台隐私保护指引未声明“选中的文件”。请管理员在微信公众平台补充该隐私类型并生效后，再从聊天记录导入 TXT。',
        confirmText: '知道了',
        showCancel: false
      });
      return;
    }
    if (code === 'empty') {
      wx.showModal({
        title: '该会话没有 TXT',
        content:
          '请先把 .txt 文件发到「文件传输助手」或该聊天，再点「从聊天记录导入 TXT」重试。',
        confirmText: '知道了',
        cancelText: '用链接导入',
        success: (res) => {
          if (!res.confirm && res.cancel) {
            this.onOpenUrlPopup();
          }
        }
      });
      return;
    }
    if (this.data.showTxtPopup || this.data.txtFilePath) {
      wx.showToast({
        title: (err && err.message) || '选择失败',
        icon: 'none',
        duration: 2800
      });
    } else {
      showChooseTxtHelpModal(this);
    }
  },

  onTapImportTxt() {
    logTxtImportDebug('tap normal import button', {
      supportTxtAgreeBtn: this.data.supportTxtAgreeBtn,
      txtNeedsPrivacyAuthorization: this.data.txtNeedsPrivacyAuthorization,
      txtPrivacyReadyHint: this.data.txtPrivacyReadyHint
    });
    this.startChooseTxtFromChat();
  },

  startChooseTxtFromChat() {
    if (!requireLogin({ message: '请先登录后导入书籍' })) {
      return;
    }
    this.setData({ txtPrivacyReadyHint: false });
    // 必须在本次点击栈内同步调起微信选文件，不能先 await 隐私检查
    this._invokeTxtFilePicker();
  },

  /**
   * 从聊天记录选 TXT：同步调起 wx.chooseMessageFile（微信：先选联系人 → 再选会话内文件）。
   */
  _invokeTxtFilePicker() {
    logTxtImportDebug('invoke chooseMessageFile', {
      running: !!this._txtPickerRunning,
      hasChooseMessageFile: typeof wx.chooseMessageFile === 'function'
    });
    if (this._txtPickerRunning) {
      wx.showToast({ title: '正在打开，请稍候', icon: 'none' });
      return;
    }
    const app = getApp();
    if (app && app.globalData) {
      app.globalData.__privacyResumeAction = 'txt_import';
    }
    this._txtPickerRunning = true;
    this.setData({ txtPickerBusy: true });

    const savedForm = { ...(this.data.txtForm || {}) };

    this._txtPickerWatchdog = setTimeout(() => {
      if (!this._txtPickerRunning) {
        return;
      }
      this.finishTxtPickerUi();
      wx.showToast({
        title: '未弹出微信选文件界面，请再点一次',
        icon: 'none',
        duration: 3000
      });
    }, 20000);

    openTxtFromChatPicker({
      onSuccess: (file) => {
        this.clearTxtPrivacyResume();
        this.applyChosenTxtFile(file, savedForm);
      },
      onFail: (err) => {
        if (!err || err.code !== 'privacy') {
          this.clearTxtPrivacyResume();
        }
        this.handleTxtPickFail(err);
      },
      onComplete: () => {
        this.finishTxtPickerUi();
      }
    });
  },

  /** 在 agreePrivacyAuthorization 回调里同步调起选文件。 */
  onWxAgreeThenPickTxt(e) {
    logTxtImportDebug('agree privacy callback', e && e.detail);
    const msg = (e.detail && e.detail.errMsg) || '';
    if (msg && !/ok/i.test(msg)) {
      return;
    }
    this.setData({
      txtPrivacyReadyHint: false,
      txtNeedsPrivacyAuthorization: false
    });
    this.startChooseTxtFromChat();
  },

  /** 低版本无 agree 按钮：先 requirePrivacyAuthorize 再选文件 */
  onTapImportTxtFallback() {
    if (!requireLogin({ message: '请先登录后导入书籍' })) {
      return;
    }
    this.setData({ txtPrivacyReadyHint: false });
    if (typeof wx.requirePrivacyAuthorize === 'function') {
      wx.requirePrivacyAuthorize({
        success: () => this._invokeTxtFilePicker(),
        fail: () => navigateToPrivacyAuthorize('txt_import')
      });
      return;
    }
    this.startChooseTxtFromChat();
  },

  onCloseTxtPopup() {
    this.setData({
      showTxtPopup: false,
      txtSubmitting: false,
      txtFilePath: '',
      txtFileName: ''
    });
  },

  onTxtFieldInput(e) {
    const field = e.currentTarget.dataset.field;
    const value = e.detail.value || '';
    this.setData({
      [`txtForm.${field}`]: value
    });
  },

  async onSubmitTxtImport() {
    const filePath = this.data.txtFilePath;
    if (!filePath) {
      wx.showToast({ title: '请先选择 TXT 文件', icon: 'none' });
      return;
    }
    const title = (this.data.txtForm.title || '').trim();
    if (!title) {
      wx.showToast({ title: '请填写书名', icon: 'none' });
      return;
    }
    this.setData({ txtSubmitting: true });
    wx.showLoading({ title: '上传中...', mask: true });
    try {
      const imported = await storeUploadTxtBook({
        filePath,
        title,
        author: (this.data.txtForm.author || '').trim()
      });
      wx.hideLoading();
      this.onCloseTxtPopup();
      wx.showToast({ title: '已导入全书', icon: 'success' });
      this.loadBooks(true);
      if (imported && imported.catalog_id) {
        wx.navigateTo({
          url: `/pages/book-detail/index?catalog_id=${encodeURIComponent(imported.catalog_id)}`
        });
      }
    } catch (error) {
      wx.hideLoading();
      wx.showToast({
        title: formatApiError(error, '导入失败'),
        icon: 'none',
        duration: 2800
      });
    } finally {
      this.setData({ txtSubmitting: false });
    }
  },

  onOpenUrlPopup() {
    if (!requireLogin({ message: '请先登录后添加链接' })) {
      return;
    }
    this.setData({
      showUrlPopup: true,
      urlForm: {
        title: '',
        author: '',
        read_url: '',
        estimated_pages: '400'
      }
    });
  },

  onCloseUrlPopup() {
    this.setData({ showUrlPopup: false });
  },

  onUrlFieldInput(e) {
    const field = e.currentTarget.dataset.field;
    const value = e.detail.value || '';
    this.setData({
      [`urlForm.${field}`]: value
    });
  },

  async onSubmitUrlImport() {
    const { title, author, read_url, estimated_pages } = this.data.urlForm;
    if (!(title || '').trim()) {
      wx.showToast({ title: '请填写书名', icon: 'none' });
      return;
    }
    if (!(read_url || '').trim()) {
      wx.showToast({ title: '请填写阅读链接', icon: 'none' });
      return;
    }
    let ep;
    const n = parseInt(String(estimated_pages || '').trim(), 10);
    if (!Number.isNaN(n) && n > 0) {
      ep = n;
    }
    this.setData({ urlSubmitting: true });
    try {
      const payload = await storeImportReadUrl({
        title: title.trim(),
        author: (author || '').trim(),
        read_url: read_url.trim(),
        estimated_pages: ep
      });
      this.onCloseUrlPopup();
      wx.showToast({
        title: payload && payload.import_mode === 'remote_text' ? '已导入全文' : '已保存链接',
        icon: 'success'
      });
      this.loadBooks(true);
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '添加失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ urlSubmitting: false });
    }
  }
});
