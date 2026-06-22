const app = getApp();

const RESUME_HINTS = {
  txt_import: '同意后将返回首页。'
};

Page({
  data: {
    referrer: '',
    resume: '',
    resumeHint: '',
    contractName: '《小程序隐私保护指引》',
    supportAgreeBtn: true
  },

  onLoad(query) {
    const resumeRaw = (query && query.resume) || '';
    const sceneRaw = (query && query.scene) || '';
    const resume = resumeRaw
      ? decodeURIComponent(resumeRaw)
      : sceneRaw === 'manual_record_file'
        ? 'txt_import'
        : sceneRaw
          ? decodeURIComponent(sceneRaw)
          : '';
    // setData 异步，onShow 可能更早执行；用实例字段避免误触发自动返回
    this._resumeKey = resume || app.globalData.__privacyResumeAction || '';
    this.setData({
      referrer: app.globalData.__privacyAuthReferrer || '',
      resume: this._resumeKey,
      resumeHint: RESUME_HINTS[this._resumeKey] || ''
    });
    this.refreshPrivacyMeta();
  },

  onShow() {
    const hasPendingAuth = typeof app.globalData.__privacyAuthResolve === 'function';
    const hasResume = !!(this._resumeKey || this.data.resume);
    if (hasPendingAuth || hasResume) {
      return;
    }
    // 误入授权页（无待处理隐私 API、无续办场景）时自动返回上一页
    const pages = typeof getCurrentPages === 'function' ? getCurrentPages() : [];
    if (pages.length > 1) {
      wx.navigateBack({ delta: 1 });
    }
  },

  refreshPrivacyMeta() {
    const supportAgreeBtn = typeof wx.canIUse === 'function'
      ? wx.canIUse('button.open-type.agreePrivacyAuthorization')
      : true;
    this.setData({ supportAgreeBtn });
    if (typeof wx.getPrivacySetting !== 'function') {
      return;
    }
    wx.getPrivacySetting({
      success: (res) => {
        this.setData({
          contractName: res.privacyContractName || '《小程序隐私保护指引》'
        });
      }
    });
  },

  onOpenContract() {
    if (typeof wx.openPrivacyContract === 'function') {
      wx.openPrivacyContract({
        fail: () => {
          wx.showToast({ title: '暂时无法打开指引', icon: 'none' });
        }
      });
      return;
    }
    wx.showToast({ title: '请升级微信后查看隐私指引', icon: 'none' });
  },

  /** 低版本基础库：用 requirePrivacyAuthorization 兜底 */
  onTapFallbackAgree() {
    if (typeof wx.requirePrivacyAuthorize === 'function') {
      wx.requirePrivacyAuthorize({
        success: () => {
          this.onAgree({ detail: { errMsg: 'agreePrivacyAuthorization:ok' } });
        },
        fail: () => {
          wx.showToast({ title: '授权未完成', icon: 'none' });
        }
      });
      return;
    }
    wx.showToast({ title: '请升级微信后重试', icon: 'none' });
  },

  onAgree(e) {
    const msg = (e.detail && e.detail.errMsg) || '';
    if (msg && !/ok/i.test(msg)) {
      return;
    }
    const resolve = app.globalData.__privacyAuthResolve;
    app.globalData.__privacyAuthHandled = true;
    app.globalData.__privacyAuthResolve = null;
    if (typeof resolve === 'function') {
      try {
        resolve({ buttonId: 'privacy-global-agree-btn', event: 'agree' });
      } catch (err) {
        // ignore
      }
    }
    const resume = this._resumeKey || this.data.resume || app.globalData.__privacyResumeAction || '';
    if (resume) {
      this._resumeKey = resume;
      app.globalData.__privacyResumeAction = resume;
    }
    wx.navigateBack({
      delta: 1,
      fail: () => {
        wx.switchTab({ url: '/pages/home/index' });
      }
    });
  },

  onDisagree() {
    app.globalData.__privacyAuthHandled = true;
    app.globalData.__privacyResumeAction = '';
    const resolve = app.globalData.__privacyAuthResolve;
    app.globalData.__privacyAuthResolve = null;
    if (typeof resolve === 'function') {
      try {
        resolve({ event: 'disagree' });
      } catch (e) {
        // ignore
      }
    }
    wx.navigateBack({
      delta: 1,
      fail: () => {
        wx.switchTab({ url: '/pages/home/index' });
      }
    });
  },

  onUnload() {
    if (app.globalData.__privacyAuthHandled) {
      app.globalData.__privacyAuthHandled = false;
      return;
    }
    const resolve = app.globalData.__privacyAuthResolve;
    app.globalData.__privacyAuthResolve = null;
    if (typeof resolve === 'function') {
      try {
        resolve({ event: 'disagree' });
      } catch (e) {
        // ignore
      }
    }
  }
});
