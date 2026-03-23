const { bindPair, createBook, createEntry, fetchHome, unbindPair } = require('../../services/api');
const { COPY, formatApiError, mapBindErrorMessage } = require('../../utils/copywriting');

const app = getApp();

Page({
  data: {
    isLogin: false,
    hasPartner: false,
    loginLoading: false,
    bindLoading: false,
    bookSubmitting: false,
    user: {
      nickname: '',
      avatar: '',
      join_code: ''
    },
    partner: {
      nickname: '',
      avatar: ''
    },
    bindCode: '',
    partnerStatusText: '绑定后就能同步看到彼此的共读进度',
    currentBook: null,
    showBookPopup: false,
    bookForm: {
      title: '',
      author: '',
      total_pages: ''
    },
    showNotePopup: false,
    noteForm: {
      page: '',
      content: ''
    },
    noteSubmitting: false
  },

  onShow() {
    this.initPage();
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({
        selected: 0
      });
    }
  },

  async initPage() {
    const user = app.globalData.user;
    if (!user || !app.globalData.token) {
      this.setData({
        isLogin: false,
        hasPartner: false,
        user: {
          nickname: '',
          avatar: '',
          join_code: ''
        },
        partner: {
          nickname: '',
          avatar: ''
        },
        currentBook: null
      });
      return;
    }

    this.setData({
      isLogin: true,
      user
    });
    await this.loadHomeData();
  },

  async loadHomeData() {
    try {
      const data = await fetchHome();
      app.globalData.user = data.user;
      app.globalData.pair = data.pair;
      app.globalData.currentBook = data.current_book;

      this.setData({
        isLogin: true,
        user: data.user,
        hasPartner: !!data.pair,
        partner: data.pair ? data.pair.partner : { nickname: '', avatar: '' },
        partnerStatusText: data.pair
          ? (data.current_book ? '你们已经绑定，可以开始同步记录进度和想法' : '已绑定成功，下一步添加一本正在共读的书')
          : '绑定后就能同步看到彼此的共读进度',
        currentBook: data.current_book || null
      });

      if (typeof this.getTabBar === 'function' && this.getTabBar()) {
        this.getTabBar().setData({
          hasBook: !!data.current_book,
          hasPartner: !!data.pair
        });
      }
    } catch (error) {
      if (error.code === 401) {
        app.logout();
      }
      wx.showToast({
        title: formatApiError(error, '首页数据加载失败'),
        icon: 'none'
      });
    }
  },

  async onTapLogin() {
    this.setData({ loginLoading: true });
    try {
      await app.loginFlow();
      await this.loadHomeData();
      wx.showToast({
        title: '登录成功',
        icon: 'success'
      });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '登录失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ loginLoading: false });
    }
  },

  onGoToPartner() {
    if (!this.data.isLogin) {
      wx.showToast({ title: COPY.common.loginRequired, icon: 'none' });
      return;
    }
    wx.switchTab({
      url: '/pages/partner/index'
    });
  },

  onCopyJoinCode() {
    if (!this.data.isLogin) {
      wx.showToast({ title: COPY.common.loginRequired, icon: 'none' });
      return;
    }
    if (!this.data.user || !this.data.user.join_code) {
      return;
    }

    wx.setClipboardData({
      data: this.data.user.join_code,
      success: () => {
        wx.showToast({
          title: '复制成功',
          icon: 'success'
        });
      }
    });
  },

  onBindCodeInput(e) {
    // 仅保留数字，确保与 6 位数字共读码规范一致
    const onlyDigits = (e.detail.value || '').replace(/\D/g, '').slice(0, 6);
    this.setData({
      bindCode: onlyDigits
    });
  },

  async onBindPartner() {
    if (!this.data.isLogin) {
      wx.showToast({ title: COPY.common.loginRequired, icon: 'none' });
      return;
    }
    const joinCode = (this.data.bindCode || '').replace(/\D/g, '').trim();
    if (!joinCode || joinCode.length !== 6) {
      wx.showToast({
        title: COPY.pair.codeInvalid,
        icon: 'none'
      });
      return;
    }

    this.setData({ bindLoading: true });
    try {
      await bindPair(joinCode);
      this.setData({ bindCode: '' });
      await this.loadHomeData();
      wx.showToast({
        title: '绑定成功',
        icon: 'success'
      });
    } catch (error) {
      wx.showToast({
        title: mapBindErrorMessage(error),
        icon: 'none'
      });
    } finally {
      this.setData({ bindLoading: false });
    }
  },

  onTapManagePair() {
    if (!this.data.isLogin) {
      wx.showToast({ title: COPY.common.loginRequired, icon: 'none' });
      return;
    }
    wx.showActionSheet({
      itemList: ['解绑伙伴'],
      success: async (res) => {
        if (res.tapIndex !== 0) {
          return;
        }

        wx.showModal({
          title: '确认解绑',
          content: '解绑后不会删除历史记录，但你们将停止同步新的共读数据。',
          success: async (modalRes) => {
            if (!modalRes.confirm) {
              return;
            }

            try {
              await unbindPair();
              await this.loadHomeData();
              wx.showToast({
                title: '已解绑',
                icon: 'success'
              });
            } catch (error) {
              wx.showToast({
                title: formatApiError(error, '解绑失败'),
                icon: 'none'
              });
            }
          }
        });
      }
    });
  },

  onTapAddBook() {
    if (!this.data.isLogin) {
      wx.showToast({ title: COPY.common.loginRequired, icon: 'none' });
      return;
    }
    if (!this.data.hasPartner) {
      wx.showToast({
        title: '请先绑定共读伙伴',
        icon: 'none'
      });
      return;
    }

    this.setData({
      showBookPopup: true
    });
  },

  onCloseBookPopup() {
    this.setData({
      showBookPopup: false,
      bookForm: {
        title: '',
        author: '',
        total_pages: ''
      }
    });
  },

  onBookFieldInput(e) {
    const { field } = e.currentTarget.dataset;
    this.setData({
      [`bookForm.${field}`]: e.detail.value
    });
  },

  async onSubmitBook() {
    const { title, author, total_pages } = this.data.bookForm;
    if (!title.trim()) {
      wx.showToast({
        title: '请填写书名',
        icon: 'none'
      });
      return;
    }

    const totalPagesInt = parseInt(total_pages, 10);
    if (!total_pages || isNaN(totalPagesInt) || totalPagesInt <= 0) {
      wx.showToast({
        title: '请填写正确的总页数',
        icon: 'none'
      });
      return;
    }

    this.setData({ bookSubmitting: true });
    try {
      await createBook({
        title: title.trim(),
        author: author.trim(),
        total_pages: totalPagesInt
      });
      this.onCloseBookPopup();
      await this.loadHomeData();
      wx.showToast({
        title: '书籍已添加',
        icon: 'success'
      });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '添加失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ bookSubmitting: false });
    }
  },

  onGotoProgress() {
    wx.navigateTo({
      url: '/pages/progress/index'
    });
  },

  onTapWriteNote() {
    if (!this.data.isLogin) {
      wx.showToast({ title: COPY.common.loginRequired, icon: 'none' });
      return;
    }
    if (!this.data.currentBook) {
      wx.showToast({ title: '请先添加正在共读的书', icon: 'none' });
      return;
    }
    this.setData({
      showNotePopup: true,
      noteForm: {
        page: this.data.currentBook.my_progress || '',
        content: ''
      }
    });
  },

  onCenterBtnClick() {
    if (!this.data.isLogin) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }
    if (!this.data.hasPartner) {
      wx.showToast({ title: '请先绑定伙伴', icon: 'none' });
      return;
    }
    if (!this.data.currentBook) {
      this.onTapAddBook();
    } else {
      this.setData({
        showNotePopup: true,
        noteForm: {
          page: this.data.currentBook.my_progress || '',
          content: ''
        }
      });
    }
  },

  onCloseNotePopup() {
    this.setData({
      showNotePopup: false,
      noteForm: { page: '', content: '' }
    });
  },

  onNotePageInput(e) {
    const onlyDigits = (e.detail.value || '').replace(/\D/g, '');
    this.setData({
      'noteForm.page': onlyDigits
    });
  },

  onNoteContentInput(e) {
    this.setData({
      'noteForm.content': e.detail.value
    });
  },

  async onSubmitNote() {
    const { page, content } = this.data.noteForm;
    const pageNum = Number(page);
    if (!page || isNaN(pageNum) || pageNum <= 0) {
      wx.showToast({ title: COPY.entry.pageInvalid, icon: 'none' });
      return;
    }
    if (this.data.currentBook && pageNum < Number(this.data.currentBook.my_progress || 0)) {
      wx.showToast({ title: COPY.entry.pageRollback, icon: 'none' });
      return;
    }
    if (this.data.currentBook && pageNum > this.data.currentBook.total_pages) {
      wx.showToast({ title: COPY.entry.pageExceed, icon: 'none' });
      return;
    }

    this.setData({ noteSubmitting: true });
    try {
      await createEntry({
        book_id:      this.data.currentBook.book_id,
        page:         pageNum,
        note_content: (content || '').trim()
      });
      this.onCloseNotePopup();
      await this.loadHomeData();
      wx.showToast({ title: '记录成功', icon: 'success' });
    } catch (error) {
      wx.showToast({ title: formatApiError(error, COPY.common.networkRetry), icon: 'none' });
    } finally {
      this.setData({ noteSubmitting: false });
    }
  }
});

