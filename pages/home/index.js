const { createBook, fetchHome, requestBookSwitch, respondBookSwitch, respondPairRequest } = require('../../services/api');
const { COPY, formatApiError } = require('../../utils/copywriting');
const { pairRequestSub, pairRequestTitle } = require('../../utils/pair-request');
const { requireLogin } = require('../../utils/auth-gate');
const { buildHomeShare, enableWechatShareMenu } = require('../../utils/share');

const app = getApp();

const clampPercent = (value) => Math.max(0, Math.min(100, value));

const getInitial = (name, fallback) => {
  const text = (name || '').trim();
  return text ? text.slice(0, 1) : fallback;
};

const normalizeBook = (book) => {
  if (!book) {
    return null;
  }

  const totalPages = Number(book.total_pages || 0);
  const myProgress = Number(book.my_progress || book.my_page || 0);
  const partnerProgress = Number(book.partner_progress || book.partner_page || 0);
  const myProgressPercent = totalPages > 0 ? clampPercent(Math.round((myProgress / totalPages) * 100)) : 0;
  const partnerProgressPercent = totalPages > 0 ? clampPercent(Math.round((partnerProgress / totalPages) * 100)) : 0;
  const diff = Math.abs(myProgress - partnerProgress);
  let relationshipTip = '今天可以各读一小段，再更新一次阅读进度。';

  if (totalPages > 0 && myProgress === 0 && partnerProgress === 0) {
    relationshipTip = '这本书刚开始，先约定一个轻松的共读节奏。';
  } else if (diff === 0 && (myProgress > 0 || partnerProgress > 0)) {
    relationshipTip = '你们读到同一位置，适合记录一次阶段进度。';
  } else if (myProgress > partnerProgress) {
    relationshipTip = `你暂时领先 ${diff} 页，可以先更新自己的阅读进度。`;
  } else if (partnerProgress > myProgress) {
    relationshipTip = `伙伴暂时领先 ${diff} 页，今天追上一小段就好。`;
  }

  return {
    ...book,
    total_pages: totalPages,
    my_progress: myProgress,
    partner_progress: partnerProgress,
    myProgressPercent,
    partnerProgressPercent,
    progressLine: totalPages > 0 ? `${myProgress}/${totalPages} 页 · ${partnerProgress}/${totalPages} 页` : '还未设置总页数',
    relationshipTip
  };
};

Page({
  data: {
    isLogin: false,
    hasPartner: false,
    loginLoading: false,
    reviewLoginLoading: false,
    showReviewLogin: false,
    showReviewLoginPanel: false,
    reviewAccount: 'reviewer',
    reviewPassword: '',
    /** 已同意微信隐私指引且勾选用户协议后可登录 */
    canProceedLogin: false,
    bookSubmitting: false,
    user: {
      nickname: '',
      avatar: '',
      join_code: ''
    },
    userInitial: '我',
    partner: {
      nickname: '',
      avatar: ''
    },
    partnerInitial: 'TA',
    currentBook: null,
    bookSwitchIncoming: null,
    bookSwitchOutgoing: null,
    switchResponding: false,
    pairRequestIncoming: null,
    pairRequestOutgoing: null,
    pairRequestTitle: '',
    pairRequestSub: '',
    pairRequestResponding: false,
    showBookPopup: false,
    bookForm: {
      title: '',
      author: '',
      total_pages: ''
    }
  },

  onShow() {
    enableWechatShareMenu();
    this.setData({
      showReviewLogin: app.globalData.apiEnvVersion !== 'release'
    });
    if (app.globalData.homeNeedsRefresh) {
      app.globalData.homeNeedsRefresh = false;
    }
    this.initPage();
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({
        selected: 0
      });
    }
  },

  // 弹窗内容区域阻止事件冒泡（WXML 的 catchtap 需要绑定方法名）
  noop() {},

  onShareAppMessage() {
    return buildHomeShare();
  },

  onShareTimeline() {
    return { title: buildHomeShare().title };
  },

  onLoginConsentChange(e) {
    const can = !!(e.detail && e.detail.canLogin);
    this.setData({ canProceedLogin: can });
  },

  onTapLoginBlocked() {
    wx.showToast({
      title: '请先完成上方隐私授权并勾选同意协议',
      icon: 'none'
    });
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
        userInitial: '我',
        partner: {
          nickname: '',
          avatar: ''
        },
        partnerInitial: 'TA',
        currentBook: null
      });
      app.syncReadingContext({
        pair: null,
        currentBook: null
      });
      return;
    }

    this.setData({
      isLogin: true,
      user,
      userInitial: getInitial(user.nickname, '我')
    });
    await this.loadHomeData();
  },

  async loadHomeData() {
    try {
      const data = await fetchHome();
      const currentBook = normalizeBook(data.current_book);
      const partner = (data.pair && data.pair.partner) || { nickname: '', avatar: '' };
      app.syncReadingContext({
        user: data.user,
        pair: data.pair,
        currentBook
      }, { persistUser: true });

      const bookSwitch = data.book_switch || {};
      const pairRequests = data.pair_requests || [];
      const pairRequestIncoming = pairRequests.find((r) => r.direction === 'incoming') || null;
      const pairRequestOutgoing = pairRequests.find((r) => r.direction === 'outgoing') || null;
      this.setData({
        isLogin: true,
        user: data.user,
        userInitial: getInitial(data.user && data.user.nickname, '我'),
        hasPartner: !!data.pair,
        partner,
        partnerInitial: getInitial(partner.nickname, 'TA'),
        currentBook,
        bookSwitchIncoming: bookSwitch.incoming || null,
        bookSwitchOutgoing: bookSwitch.outgoing || null,
        pairRequestIncoming,
        pairRequestOutgoing,
        pairRequestTitle: pairRequestIncoming
          ? pairRequestTitle(pairRequestIncoming)
          : (pairRequestOutgoing ? pairRequestTitle(pairRequestOutgoing) : ''),
        pairRequestSub: pairRequestIncoming
          ? pairRequestSub(pairRequestIncoming)
          : (pairRequestOutgoing ? pairRequestSub(pairRequestOutgoing) : '')
      });

      if (typeof this.getTabBar === 'function' && this.getTabBar()) {
        this.getTabBar().setData({
          hasBook: !!currentBook,
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
    if (!this.data.canProceedLogin) {
      this.onTapLoginBlocked();
      return;
    }
    if (this.data.loginLoading) {
      return;
    }
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

  onOpenReviewLogin() {
    if (!this.data.canProceedLogin) {
      this.onTapLoginBlocked();
      return;
    }
    this.setData({
      showReviewLoginPanel: true,
      reviewAccount: this.data.reviewAccount || 'reviewer',
      reviewPassword: ''
    });
  },

  onCloseReviewLogin() {
    this.setData({
      showReviewLoginPanel: false,
      reviewPassword: ''
    });
  },

  onReviewAccountInput(e) {
    this.setData({ reviewAccount: e.detail.value || '' });
  },

  onReviewPasswordInput(e) {
    this.setData({ reviewPassword: e.detail.value || '' });
  },

  async onSubmitReviewLogin() {
    if (this.data.reviewLoginLoading) {
      return;
    }
    const account = (this.data.reviewAccount || '').trim();
    const password = this.data.reviewPassword || '';
    if (!account || !password) {
      wx.showToast({ title: '请输入账号和密码', icon: 'none' });
      return;
    }

    this.setData({ reviewLoginLoading: true });
    try {
      await app.reviewLoginFlow(account, password);
      this.onCloseReviewLogin();
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
      this.setData({ reviewLoginLoading: false });
    }
  },

  onGoToPartner() {
    if (!this.data.isLogin) {
      wx.showToast({ title: COPY.common.loginRequired, icon: 'none' });
      return;
    }
    wx.navigateTo({
      url: '/pages/partner/index'
    });
  },

  onGoToManualAdd() {
    this.onTapAddBook();
  },

  onGoProfileLogin() {
    wx.switchTab({ url: '/pages/profile/index' });
  },

  onPreviewManualRecord() {
    wx.showModal({
      title: '记录方式',
      content: '添加书名、作者和页数后，可保存页码、状态和备注。',
      showCancel: false,
      confirmText: '我知道了'
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

    const needSwitchRequest = !!this.data.currentBook;
    const doCreate = async () => {
      const result = await createBook({
        title: title.trim(),
        author: author.trim(),
        total_pages: totalPagesInt
      });
      this.onCloseBookPopup();
      app.globalData.homeNeedsRefresh = true;
      await this.loadHomeData();
      if (result && result.mode === 'switch_request') {
        wx.showToast({ title: '已申请，等待伙伴同意', icon: 'none' });
        return;
      }
      wx.showToast({ title: '已添加', icon: 'success' });
    };
    const doSwitchRequest = async () => {
      const result = await requestBookSwitch({
        title: title.trim(),
        author: author.trim(),
        total_pages: totalPagesInt
      });
      this.onCloseBookPopup();
      app.globalData.homeNeedsRefresh = true;
      await this.loadHomeData();
      wx.showToast({
        title: result && result.mode === 'book' ? '已切换' : '已申请',
        icon: 'success'
      });
    };

    if (needSwitchRequest) {
      const cur = this.data.currentBook;
      wx.showModal({
        title: '申请换书',
        content: `当前在读《${cur.title || '共读书'}》，换书需伙伴同意，确认申请吗？`,
        confirmText: '申请',
        success: async (res) => {
          if (!res.confirm) {
            return;
          }
          this.setData({ bookSubmitting: true });
          try {
            await doSwitchRequest();
          } catch (error) {
            wx.showToast({
              title: formatApiError(error, '申请失败'),
              icon: 'none'
            });
          } finally {
            this.setData({ bookSubmitting: false });
          }
        }
      });
      return;
    }

    this.setData({ bookSubmitting: true });
    try {
      await doCreate();
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '添加失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ bookSubmitting: false });
    }
  },

  async onApproveBookSwitch() {
    const req = this.data.bookSwitchIncoming;
    if (!req || !req.request_id || this.data.switchResponding) {
      return;
    }
    this.setData({ switchResponding: true });
    try {
      const result = await respondBookSwitch(req.request_id, 'approve');
      app.globalData.homeNeedsRefresh = true;
      if (result && result.book) {
        app.syncCurrentBook(normalizeBook(result.book));
      }
      await this.loadHomeData();
      wx.showToast({ title: '已同意', icon: 'success' });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '操作失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ switchResponding: false });
    }
  },

  async onRejectBookSwitch() {
    const req = this.data.bookSwitchIncoming;
    if (!req || !req.request_id || this.data.switchResponding) {
      return;
    }
    this.setData({ switchResponding: true });
    try {
      await respondBookSwitch(req.request_id, 'reject');
      app.globalData.homeNeedsRefresh = true;
      await this.loadHomeData();
      wx.showToast({ title: '已拒绝', icon: 'none' });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '操作失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ switchResponding: false });
    }
  },

  onGotoProgress() {
    if (!requireLogin({ message: COPY.common.loginRequired })) {
      return;
    }
    wx.switchTab({
      url: '/pages/progress/index'
    });
  },

  onGoShareCircle() {
    wx.showToast({ title: '该功能暂不可用', icon: 'none' });
  },

  onOpenCurrentBook() {
    if (!requireLogin({ message: COPY.common.loginRequired })) {
      return;
    }
    const book = this.data.currentBook;
    if (!book || !book.book_id) {
      return;
    }
    wx.switchTab({
      url: '/pages/progress/index'
    });
  },

  onRecordToday() {
    if (!requireLogin({ message: COPY.common.loginRequired })) {
      return;
    }
    app.globalData.openProgressComposer = true;
    wx.switchTab({
      url: '/pages/progress/index'
    });
  },

  onGoManagePartner() {
    this.onGoToPartner();
  },

  onCenterBtnClick() {
    if (!this.data.isLogin) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }
    if (!this.data.hasPartner) {
      this.onGoToPartner();
      return;
    }
    if (!this.data.currentBook) {
      this.onTapAddBook();
    } else {
      this.onRecordToday();
    }
  },

  async onApprovePairRequest() {
    const req = this.data.pairRequestIncoming;
    if (!req || !req.request_id || this.data.pairRequestResponding) {
      return;
    }
    this.setData({ pairRequestResponding: true });
    try {
      const result = await respondPairRequest(req.request_id, 'approve');
      app.globalData.homeNeedsRefresh = true;
      if (result && result.pair) {
        app.syncReadingContext({ pair: result.pair });
      } else if (req.request_type === 'unbind') {
        app.syncReadingContext({ pair: null, currentBook: null });
      }
      await this.loadHomeData();
      wx.showToast({
        title: req.request_type === 'bind' ? '已同意绑定' : '已同意解绑',
        icon: 'success'
      });
    } catch (error) {
      wx.showToast({ title: formatApiError(error, '操作失败'), icon: 'none' });
    } finally {
      this.setData({ pairRequestResponding: false });
    }
  },

  async onRejectPairRequest() {
    const req = this.data.pairRequestIncoming;
    if (!req || !req.request_id || this.data.pairRequestResponding) {
      return;
    }
    this.setData({ pairRequestResponding: true });
    try {
      await respondPairRequest(req.request_id, 'reject');
      app.globalData.homeNeedsRefresh = true;
      await this.loadHomeData();
      wx.showToast({ title: '已拒绝', icon: 'none' });
    } catch (error) {
      wx.showToast({ title: formatApiError(error, '操作失败'), icon: 'none' });
    } finally {
      this.setData({ pairRequestResponding: false });
    }
  }
});
