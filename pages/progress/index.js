const { createEntry, fetchBookEntries, fetchHome, markBookEntriesRead, replyEntry } = require('../../services/api');
const { COPY, formatApiError } = require('../../utils/copywriting');
const { requireLogin } = require('../../utils/auth-gate');
const { openReportPage } = require('../../utils/report-nav');
const { navigateTo: safeNavigateTo } = require('../../utils/safe-navigate');
const { buildReaderUrl } = require('../../utils/reading-progress-cache');
const { isSocialSharingEnabled } = require('../../utils/feature-flags');

const app = getApp();

const getInitial = (name, fallback) => {
  const text = (name || '').trim();
  return text ? text.slice(0, 1) : fallback;
};

Page({
  data: {
    book: null,
    entries: [],
    unreadCount: 0,
    entryPage: 1,
    entryPageSize: 30,
    entryHasMore: false,
    entryLoadingMore: false,
    loading: false,
    // 当前用户和伙伴信息（用于进度条头像）
    user: { nickname: '', avatar: '' },
    userInitial: '我',
    partner: { nickname: '', avatar: '' },
    partnerInitial: 'TA',
    showComposer: false,
    entrySubmitting: false,
    entryForm: {
      page: '',
      note_content: '',
      quote_text: '',
      mark_finished: false
    },
    showReplyPopup: false,
    replySubmitting: false,
    replyContent: '',
    activeReplyEntryId: '',
    activeReplyQuote: '',
    activeReplyNote: '',
    showSharePopup: false,
    shareSubmitting: false,
    shareExcerpt: '',
    shareConfirmed: false,
    sharePage: '',
    activeShareEntryId: '',
    locateQueue: [],
    scrollIntoViewId: ''
  },

  // 弹窗内容区域阻止事件冒泡（WXML 的 catchtap 需要绑定方法名）
  noop() {},

  /** 内置书城书目：进入正文阅读器（沿用当前「我的进度」页码） */
  onTapOpenPairReader() {
    const book = this.data.book;
    if (!book || !book.catalog_id) {
      return;
    }
    const cid = book.catalog_id;
    safeNavigateTo(buildReaderUrl(cid, { page: book.my_progress || 0 }), this);
  },

  onLoad(query) {
    this.shouldOpenComposer = !!(query && query.open_composer === '1');
  },

  onShow() {
    if (!requireLogin({ message: '请先登录后查看进度' })) {
      return;
    }
    if (app.globalData.openProgressComposer) {
      app.globalData.openProgressComposer = false;
      this.shouldOpenComposer = true;
    }
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({
        selected: 2,
        hasPartner: !!app.globalData.pair,
        hasBook: !!app.globalData.currentBook
      });
    }
    this.loadPageData();
  },

  async loadPageData() {
    if (!app.globalData.user || !app.globalData.token) {
      this.setData({
        book: null,
        entries: [],
        unreadCount: 0,
        user: { nickname: '', avatar: '' },
        userInitial: '我',
        partner: { nickname: '', avatar: '' },
        partnerInitial: 'TA'
      });
      return;
    }

    this.setData({ loading: true });
    try {
      const homeData = await fetchHome();
      const pair = homeData.pair || null;
      const currentUser = homeData.user || null;
      const rawBook = homeData.current_book || null;

      app.syncReadingContext({
        user: currentUser,
        pair,
        currentBook: rawBook
      }, { persistUser: true });

      const partner = pair ? (pair.partner || {}) : {};
      const book = this.decorateBook(rawBook);
      if (!book) {
        app.syncCurrentBook(null);
        this.setData({
          book: null,
          entries: [],
          unreadCount: 0,
          entryPage: 1,
          entryHasMore: false,
          user: { nickname: currentUser && currentUser.nickname || '', avatar: currentUser && currentUser.avatar || '' },
          userInitial: getInitial(currentUser && currentUser.nickname, '我'),
          partner: { nickname: partner.nickname || '', avatar: partner.avatar || '' },
          partnerInitial: getInitial(partner.nickname, 'TA')
        });
        return;
      }

      const entriesRes = await fetchBookEntries(book.book_id, 1, this.data.entryPageSize);
      const normalizedEntries = (entriesRes.entries || []).map((item) => this.normalizeEntryItem(item, currentUser));
      const unreadQueue = normalizedEntries
        .filter((item) => item.is_unread)
        .map((item) => `entry-${item.entry_id}`);

      this.setData({
        book,
        entries: normalizedEntries,
        unreadCount: entriesRes.unread_count || 0,
        locateQueue: unreadQueue,
        entryPage: 1,
        entryHasMore: !!(entriesRes.pagination && entriesRes.pagination.has_more),
        user: { nickname: currentUser && currentUser.nickname || '', avatar: currentUser && currentUser.avatar || '' },
        userInitial: getInitial(currentUser && currentUser.nickname, '我'),
        partner: { nickname: partner.nickname || '', avatar: partner.avatar || '' },
        partnerInitial: getInitial(partner.nickname, 'TA')
      });
      // 联调阶段严格要求后端接口可用，进入页面即同步已读状态
      await this.syncEntriesRead(book.book_id, normalizedEntries);
      app.syncCurrentBook(book);
      if (this.shouldOpenComposer) {
        this.shouldOpenComposer = false;
        this.onOpenComposer();
      }
    } catch (error) {
      if (error.code === 401) {
        app.logout();
      }
      wx.showToast({
        title: formatApiError(error, '加载进度失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ loading: false });
    }
  },

  decorateBook(rawBook) {
    if (!rawBook) {
      return null;
    }
    const totalPages = Number(rawBook.total_pages || 0);
    const myProgress = Number(rawBook.my_progress || 0);
    const partnerProgress = Number(rawBook.partner_progress || 0);
    const safeTotal = totalPages > 0 ? totalPages : 1;
    const myPercent = Math.min(100, Math.max(0, Math.round((myProgress / safeTotal) * 100)));
    const partnerPercent = Math.min(100, Math.max(0, Math.round((partnerProgress / safeTotal) * 100)));
    const gap = myProgress - partnerProgress;
    let progressSummary = '你们进度一致';
    if (gap > 0) {
      progressSummary = `你领先 ${gap} 页`;
    } else if (gap < 0) {
      progressSummary = `你落后 ${Math.abs(gap)} 页`;
    }
    return {
      ...rawBook,
      my_progress_percent: myPercent,
      partner_progress_percent: partnerPercent,
      my_finished:
        typeof rawBook.my_finished === 'boolean'
          ? rawBook.my_finished
          : totalPages > 0 && myProgress >= totalPages,
      partner_finished:
        typeof rawBook.partner_finished === 'boolean'
          ? rawBook.partner_finished
          : totalPages > 0 && partnerProgress >= totalPages,
      progress_summary: progressSummary
    };
  },

  formatTime(timeStr) {
    if (!timeStr) {
      return '';
    }
    const date = new Date(timeStr);
    if (Number.isNaN(date.getTime())) {
      return timeStr;
    }
    const y = date.getFullYear();
    const m = `${date.getMonth() + 1}`.padStart(2, '0');
    const d = `${date.getDate()}`.padStart(2, '0');
    const hh = `${date.getHours()}`.padStart(2, '0');
    const mm = `${date.getMinutes()}`.padStart(2, '0');
    return `${y}-${m}-${d} ${hh}:${mm}`;
  },

  onBackHome() {
    wx.switchTab({
      url: '/pages/home/index'
    });
  },

  normalizeEntryItem(item, currentUser) {
    const unlockPage = item.unlock_at_page || item.page;
    const myUserId = currentUser && currentUser.user_id;
    const replies = (item.replies || []).map((reply) => ({
      ...reply,
      is_mine: reply.user_id === myUserId,
      replyInitial: getInitial(reply.nickname, '书'),
      created_at: this.formatTime(reply.created_at)
    }));
    return {
      ...item,
      unlock_at_page: unlockPage,
      anchor_id: `entry-${item.entry_id}`,
      entryInitial: getInitial(item.nickname, item.is_mine ? '我' : 'TA'),
      created_at: this.formatTime(item.created_at),
      replies,
      has_quote: !!(item.quote_text && String(item.quote_text).trim()),
      has_comment: !!(item.note_content && String(item.note_content).trim())
    };
  },

  buildEntryFormDefaults() {
    const book = this.data.book;
    const pending = app.globalData.pendingEntryQuote;
    if (pending) {
      app.globalData.pendingEntryQuote = null;
    }
    const defaultPage = pending && pending.page
      ? String(pending.page)
      : (book && book.my_progress ? String(book.my_progress) : '');
    return {
      page: defaultPage,
      note_content: '',
      quote_text: pending && pending.quote_text ? pending.quote_text : '',
      mark_finished: false
    };
  },

  onOpenComposer() {
    if (!app.globalData.token) {
      wx.showToast({ title: COPY.common.loginRequired, icon: 'none' });
      return;
    }
    if (!this.data.book) {
      return;
    }
    this.setData({
      showComposer: true,
      entryForm: this.buildEntryFormDefaults()
    });
  },

  onCenterBtnClick() {
    this.onOpenComposer();
  },

  onCloseComposer() {
    this.setData({
      showComposer: false,
      entryForm: {
        page: '',
        note_content: '',
        quote_text: '',
        mark_finished: false
      }
    });
  },

  onClearQuote() {
    this.setData({ 'entryForm.quote_text': '' });
  },

  onEntryFieldInput(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({
      [`entryForm.${field}`]: e.detail.value
    });
  },

  onToggleFinished() {
    this.setData({
      'entryForm.mark_finished': !this.data.entryForm.mark_finished
    });
  },

  async onSubmitEntry() {
    const { book, entryForm } = this.data;
    if (!book) {
      return;
    }

    const pageInt = parseInt(entryForm.page, 10);
    if (!entryForm.mark_finished) {
      if (isNaN(pageInt) || pageInt <= 0) {
        wx.showToast({
          title: COPY.entry.pageInvalid,
          icon: 'none'
        });
        return;
      }
      if (pageInt < Number(book.my_progress || 0)) {
        wx.showToast({
          title: COPY.entry.pageRollback,
          icon: 'none'
        });
        return;
      }
      if (book.total_pages > 0 && pageInt > book.total_pages) {
        wx.showToast({
          title: COPY.entry.pageExceed,
          icon: 'none'
        });
        return;
      }
    }

    this.setData({ entrySubmitting: true });
    try {
      const quoteText = (entryForm.quote_text || '').trim();
      const noteContent = (entryForm.note_content || '').trim();
      if (!entryForm.mark_finished && !quoteText && !noteContent) {
        wx.showToast({ title: '请填写页码或阅读备注', icon: 'none' });
        return;
      }
      await createEntry({
        book_id: book.book_id,
        page: entryForm.mark_finished ? book.total_pages : pageInt,
        note_content: noteContent,
        quote_text: quoteText,
        mark_finished: !!entryForm.mark_finished
      });
      this.onCloseComposer();
      await this.loadPageData();
      wx.showToast({
        title: '更新成功',
        icon: 'success'
      });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '提交失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ entrySubmitting: false });
    }
  },

  onTapEntryBody(e) {
    if (!e.currentTarget.dataset.isLocked) {
      return;
    }
    const unlockPage = e.currentTarget.dataset.page || 0;
    wx.vibrateShort();
    wx.showToast({
      title: COPY.entry.lockHint.replace('{page}', unlockPage),
      icon: 'none'
    });
  },

  onLocateNextUnread() {
    const queue = this.data.locateQueue || [];
    if (!queue.length) {
      wx.showToast({ title: '没有未读更新', icon: 'none' });
      return;
    }
    const [currentId, ...rest] = queue;
    this.setData({
      locateQueue: rest,
      unreadCount: Math.max(0, Number(this.data.unreadCount || 0) - 1),
      scrollIntoViewId: currentId
    });
    this.syncEntriesRead(this.data.book && this.data.book.book_id, this.data.entries);
    wx.vibrateShort();
  },

  async syncEntriesRead(bookId, entries) {
    if (!bookId || !entries || !entries.length) {
      return;
    }
    const lastEntryId = entries[entries.length - 1].entry_id;
    await markBookEntriesRead(bookId, lastEntryId);
  },

  async onLoadMoreEntries() {
    if (!this.data.book || this.data.entryLoadingMore || !this.data.entryHasMore) {
      return;
    }
    this.setData({ entryLoadingMore: true });
    try {
      const nextPage = this.data.entryPage + 1;
      const payload = await fetchBookEntries(this.data.book.book_id, nextPage, this.data.entryPageSize);
      const moreEntries = (payload.entries || []).map((item) => this.normalizeEntryItem(item, app.globalData.user));
      this.setData({
        entries: this.data.entries.concat(moreEntries),
        entryPage: nextPage,
        entryHasMore: !!(payload.pagination && payload.pagination.has_more)
      });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '加载更多失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ entryLoadingMore: false });
    }
  },

  onOpenReplyPopup(e) {
    const entryId = e.currentTarget.dataset.entryId;
    const entry = (this.data.entries || []).find((item) => item.entry_id === entryId) || {};
    this.setData({
      showReplyPopup: true,
      activeReplyEntryId: entryId,
      activeReplyQuote: entry.quote_text || '',
      activeReplyNote: entry.note_content || '',
      replyContent: ''
    });
  },

  onCloseReplyPopup() {
    this.setData({
      showReplyPopup: false,
      activeReplyEntryId: '',
      activeReplyQuote: '',
      activeReplyNote: '',
      replyContent: ''
    });
  },

  onReplyInput(e) {
    this.setData({
      replyContent: e.detail.value
    });
  },

  async onSubmitReply() {
    const content = (this.data.replyContent || '').trim();
    if (!content) {
      wx.showToast({
        title: '请输入补充备注',
        icon: 'none'
      });
      return;
    }

    this.setData({ replySubmitting: true });
    try {
      await replyEntry(this.data.activeReplyEntryId, content);
      this.onCloseReplyPopup();
      await this.loadPageData();
      wx.showToast({
        title: '备注已保存',
        icon: 'success'
      });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '保存备注失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ replySubmitting: false });
    }
  },

  onOpenSharePopup(e) {
    if (!isSocialSharingEnabled()) {
      wx.showToast({ title: '该功能暂不可用', icon: 'none' });
      return;
    }
    const note = (e.currentTarget.dataset.note || '').trim();
    const quote = (e.currentTarget.dataset.quote || '').trim();
    const page = e.currentTarget.dataset.page || '';
    const fallback = note || quote || `读到第 ${page} 页`;
    this.setData({
      showSharePopup: true,
      activeShareEntryId: e.currentTarget.dataset.entryId,
      shareExcerpt: fallback.slice(0, 300),
      sharePage: page,
      shareConfirmed: false
    });
  },

  onCloseSharePopup() {
    this.setData({
      showSharePopup: false,
      activeShareEntryId: '',
      shareExcerpt: '',
      shareConfirmed: false
    });
  },

  onShareExcerptInput(e) {
    this.setData({ shareExcerpt: e.detail.value });
  },

  onToggleShareConfirm() {
    this.setData({ shareConfirmed: !this.data.shareConfirmed });
  },

  async onSubmitShare() {
    wx.showToast({ title: '该功能暂不可用', icon: 'none' });
  },

  onGoShareCircle() {
    wx.showToast({ title: '该功能暂不可用', icon: 'none' });
  },

  onReportEntry(e) {
    const dataset = (e.currentTarget && e.currentTarget.dataset) || {};
    openReportPage({
      targetType: 'entry',
      targetId: dataset.entryId || '',
      targetUserId: dataset.userId || '',
      hint: `${dataset.nickname || '用户'} 的进度记录`,
      snapshot: dataset.snapshot || ''
    });
  },

  onReportReply(e) {
    const dataset = (e.currentTarget && e.currentTarget.dataset) || {};
    openReportPage({
      targetType: 'reply',
      targetId: dataset.replyId || '',
      targetUserId: dataset.userId || '',
      hint: `${dataset.nickname || '用户'} 的补充备注`,
      snapshot: dataset.content || ''
    });
  }
});
