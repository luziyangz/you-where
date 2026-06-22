// 登录前合规：微信平台隐私授权 + 用户协议勾选
Component({
  data: {
    agreedTerms: false,
    needWxPrivacy: false,
    privacyContractName: '《小程序隐私保护指引》',
    supportAgreeBtn: true
  },

  lifetimes: {
    attached() {
      const supportAgreeBtn = typeof wx.canIUse === 'function'
        ? wx.canIUse('button.open-type.agreePrivacyAuthorization')
        : true;
      this.setData({ supportAgreeBtn });
      this.refreshWxPrivacySetting();
    }
  },

  pageLifetimes: {
    show() {
      // 从设置返回后可能已撤回授权，需重新检测
      this.refreshWxPrivacySetting();
    }
  },

  methods: {
    refreshWxPrivacySetting() {
      if (typeof wx.getPrivacySetting !== 'function') {
        this.setData({ needWxPrivacy: false }, () => this.emitStatus());
        return;
      }
      wx.getPrivacySetting({
        success: (res) => {
          this.setData(
            {
              needWxPrivacy: !!res.needAuthorization,
              privacyContractName: res.privacyContractName || '《小程序隐私保护指引》'
            },
            () => this.emitStatus()
          );
        },
        fail: () => {
          this.setData({ needWxPrivacy: false }, () => this.emitStatus());
        }
      });
    },

    emitStatus() {
      const canLogin = !!this.data.agreedTerms && !this.data.needWxPrivacy;
      this.triggerEvent('statuschange', {
        canLogin,
        agreedTerms: this.data.agreedTerms,
        needWxPrivacy: this.data.needWxPrivacy
      });
    },

    toggleTerms() {
      this.setData({ agreedTerms: !this.data.agreedTerms }, () => this.emitStatus());
    },

    goUserAgreement() {
      wx.navigateTo({ url: '/pages/user-agreement/index' });
    },

    goPrivacyPolicy() {
      wx.navigateTo({ url: '/pages/privacy-policy/index' });
    },

    onOpenWxPrivacyContract() {
      if (typeof wx.openPrivacyContract === 'function') {
        wx.openPrivacyContract({
          fail: () => {
            wx.showToast({ title: '暂无法打开指引，请稍后重试', icon: 'none' });
          }
        });
      }
    },

    onWxPrivacyAgreed(e) {
      const msg = (e.detail && e.detail.errMsg) || '';
      if (msg && !/ok/i.test(msg)) {
        return;
      }
      this.refreshWxPrivacySetting();
    },

    /** 低版本基础库：用 requirePrivacyAuthorize 兜底同意 */
    onFallbackWxPrivacyAgree() {
      if (typeof wx.requirePrivacyAuthorize === 'function') {
        wx.requirePrivacyAuthorize({
          success: () => {
            this.onWxPrivacyAgreed({ detail: { errMsg: 'agreePrivacyAuthorization:ok' } });
          },
          fail: () => {
            wx.showToast({ title: '授权未完成', icon: 'none' });
          }
        });
        return;
      }
      wx.navigateTo({ url: '/pages/privacy-authorize/index' });
    }
  }
});
