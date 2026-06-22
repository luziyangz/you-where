// 未登录时仅允许：首页（登录入口）、用户协议、隐私政策、微信隐私授权页
const HOME_PATH = '/pages/home/index';
const HOME_ROUTE = 'pages/home/index';
let navigationGuardInstalled = false;

const TAB_ROUTES = new Set([
  'pages/home/index',
  'pages/reading-history/index',
  'pages/progress/index',
  'pages/profile/index'
]);

const PUBLIC_ROUTES = new Set([
  HOME_ROUTE,
  'pages/profile/index',
  'pages/privacy-policy/index',
  'pages/user-agreement/index',
  'pages/privacy-authorize/index'
]);

const normalizeRoute = (url) => {
  const rawUrl = typeof url === 'string' ? url : '';
  return rawUrl.split('?')[0].replace(/^\/+/, '');
};

const isPublicUrl = (url) => {
  return PUBLIC_ROUTES.has(normalizeRoute(url));
};

const isLoggedIn = () => {
  const app = getApp();
  return !!(app && app.globalData && app.globalData.token && app.globalData.user);
};

/**
 * 业务页准入：未登录时 toast，并从 Tab 子页 switchTab 首页，非 Tab 页 reLaunch 清空栈，避免返回进入受限页。
 */
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
  const route = pages.length ? pages[pages.length - 1].route : '';
  if (route === HOME_ROUTE) {
    return false;
  }
  if (TAB_ROUTES.has(route)) {
    wx.switchTab({ url: HOME_PATH });
  } else {
    wx.reLaunch({ url: HOME_PATH });
  }
  return false;
};

/**
 * App.onShow：未登录且不在白名单页时，一律回到首页（防止栈底残留子页、扫码直达等绕过）。
 */
const enforceLoginForAppShow = () => {
  if (isLoggedIn()) {
    return;
  }
  const pages = typeof getCurrentPages === 'function' ? getCurrentPages() : [];
  if (!pages.length) {
    return;
  }
  const route = pages[pages.length - 1].route || '';
  if (PUBLIC_ROUTES.has(route)) {
    return;
  }
  wx.reLaunch({ url: HOME_PATH });
};

/**
 * 全局导航守卫：未登录时禁止进入任何业务页。页面自己的 requireLogin 仍保留，
 * 这里兜底拦截漏掉登录判断的按钮、深层入口和后续新增跳转。
 */
const installNavigationGuard = () => {
  if (navigationGuardInstalled) {
    return;
  }
  navigationGuardInstalled = true;

  const originals = {
    navigateTo: wx.navigateTo,
    redirectTo: wx.redirectTo,
    reLaunch: wx.reLaunch,
    switchTab: wx.switchTab
  };

  const redirectHomeIfNeeded = () => {
    const pages = typeof getCurrentPages === 'function' ? getCurrentPages() : [];
    const currentRoute = pages.length ? pages[pages.length - 1].route : '';
    if (currentRoute === HOME_ROUTE) {
      return;
    }
    if (TAB_ROUTES.has(currentRoute) && typeof originals.switchTab === 'function') {
      originals.switchTab.call(wx, { url: HOME_PATH });
      return;
    }
    if (typeof originals.reLaunch === 'function') {
      originals.reLaunch.call(wx, { url: HOME_PATH });
    }
  };

  const shouldBlock = (options) => {
    const url = options && options.url;
    return !!url && !isLoggedIn() && !isPublicUrl(url);
  };

  const blockNavigation = () => {
    wx.showToast({
      title: '请先登录后使用',
      icon: 'none'
    });
    redirectHomeIfNeeded();
  };

  ['navigateTo', 'redirectTo', 'reLaunch', 'switchTab'].forEach((method) => {
    if (typeof originals[method] !== 'function') {
      return;
    }
    wx[method] = function guardedNavigate(options = {}) {
      if (shouldBlock(options)) {
        blockNavigation();
        return;
      }
      return originals[method].call(wx, options);
    };
  });
};

module.exports = {
  HOME_PATH,
  PUBLIC_ROUTES,
  isLoggedIn,
  requireLogin,
  enforceLoginForAppShow,
  installNavigationGuard,
  isPublicUrl
};
