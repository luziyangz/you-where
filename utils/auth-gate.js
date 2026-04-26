const HOME_PAGE = '/pages/home/index';

const isLoggedIn = () => {
  const app = getApp();
  return !!(app && app.globalData && app.globalData.token && app.globalData.user);
};

const requireLogin = (options = {}) => {
  if (isLoggedIn()) {
    return true;
  }

  if (options.message) {
    wx.showToast({
      title: options.message,
      icon: 'none'
    });
  }

  const pages = typeof getCurrentPages === 'function' ? getCurrentPages() : [];
  const current = pages.length ? `/${pages[pages.length - 1].route}` : '';
  if (current !== HOME_PAGE) {
    wx.switchTab({ url: HOME_PAGE });
  }
  return false;
};

module.exports = {
  isLoggedIn,
  requireLogin
};
