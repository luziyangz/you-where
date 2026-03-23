const { createEntry, fetchBookEntries, fetchCurrentBook, markBookEntriesRead, replyEntry } = require('../../services/api');
const { COPY, formatApiError } = require('../../utils/copywriting');

const app = getApp();

Page({
  data: {
    book: null,
    entries: [],
    unreadCount: 0,
    loading: false,
    // 当前用户和伙伴信息（用于进度条头像）
    user: { nickname: '', avatar: '' },
    partner: { nickname: '', avatar: '' },
    showComposer: false,
    entrySubmitting: false,
    entryForm: {
      page: '',
      note_content: '',
      mark_finished: false
    },
    showReplyPopup: false,
    replySubmitting: false,
    replyContent: '',
    activeReplyEntryId: '',
    locateQueue: [],
    scrollIntoViewId: ''
  },

  onShow() {
    this.loadPageData();
  },

  async loadPageData() {
    if (!app.globalData.user || !app.globalData.token) {
      this.setData({
        book: null,
        entries: [],
        unreadCount: 0,
        user: { nickname: '', avatar: '' },
        partner: { nickname: '', avatar: '' }
      });
      return;
    }

    // 从全局数据同步 user 和 partner 头像信息
    const globalUser    = app.globalData.user    || {};
    const globalPair    = app.globalData.pair    || null;
    const globalPartner = globalPair ? (globalPair.partner || {}) : {};

    this.setData({
      user:    { nickname: globalUser.nickname    || '', avatar: globalUser.avatar    || '' },
      partner: { nickname: globalPartner.nickname || '', avatar: globalPartner.avatar || '' }
    });

    this.setData({ loading: true });
    try {
      const currentBookRes = await fetchCurrentBook();
      const book = currentBookRes.book || null;
      if (!book) {
        this.setData({
          book: null,
          entries: [],
          unreadCount: 0
        });
        return;
      }

      const entriesRes = await fetchBookEntries(book.book_id);
      const normalizedEntries = (entriesRes.entries || []).map((item) => {
        const unlockPage = item.unlock_at_page || item.page;
        return {
          ...item,
          unlock_at_page: unlockPage,
          anchor_id: `entry-${item.entry_id}`,
          created_at: this.formatTime(item.created_at)
        };
      });
      const unreadQueue = normalizedEntries
        .filter((item) => item.is_unread)
        .map((item) => `entry-${item.entry_id}`);

      this.setData({
        book,
        entries: normalizedEntries,
        unreadCount: entriesRes.unread_count || 0,
        locateQueue: unreadQueue
      });
      // 联调阶段严格要求后端接口可用，进入页面即同步已读状态
      await this.syncEntriesRead(book.book_id, normalizedEntries);
      app.globalData.currentBook = book;
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
      entryForm: {
        page: this.data.book.my_progress ? String(this.data.book.my_progress) : '',
        note_content: '',
        mark_finished: false
      }
    });
  },

  onCloseComposer() {
    this.setData({
      showComposer: false,
      entryForm: {
        page: '',
        note_content: '',
        mark_finished: false
      }
    });
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
      if (pageInt > book.total_pages) {
        wx.showToast({
          title: COPY.entry.pageExceed,
          icon: 'none'
        });
        return;
      }
    }

    this.setData({ entrySubmitting: true });
    try {
      await createEntry({
        book_id: book.book_id,
        page: entryForm.mark_finished ? book.total_pages : pageInt,
        note_content: (entryForm.note_content || '').trim(),
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
      wx.showToast({ title: '没有未读动态', icon: 'none' });
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

  onOpenReplyPopup(e) {
    this.setData({
      showReplyPopup: true,
      activeReplyEntryId: e.currentTarget.dataset.entryId,
      replyContent: ''
    });
  },

  onCloseReplyPopup() {
    this.setData({
      showReplyPopup: false,
      activeReplyEntryId: '',
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
        title: '请输入回复内容',
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
        title: '回复已发送',
        icon: 'success'
      });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '回复失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ replySubmitting: false });
    }
  }
});