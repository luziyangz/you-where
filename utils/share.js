/** 右上角菜单：统一标题与路径 */

const APP_SHARE_TITLE = '你在哪页 · 和重要的人一起读书';
const DEFAULT_SHARE_PATH = '/pages/home/index';

const enableWechatShareMenu = () => {
  if (typeof wx.hideShareMenu !== 'function') {
    return;
  }
  wx.hideShareMenu({
    menus: ['shareAppMessage', 'shareTimeline']
  });
};

const buildAppShare = (overrides = {}) => ({
  title: overrides.title || APP_SHARE_TITLE,
  path: overrides.path || DEFAULT_SHARE_PATH,
  imageUrl: overrides.imageUrl || ''
});

const buildHomeShare = () => buildAppShare({
  title: '邀请你一起记录阅读进度',
  path: DEFAULT_SHARE_PATH
});

const buildProgressToolShare = () => buildAppShare({
  title: '来看看这个阅读进度工具',
  path: DEFAULT_SHARE_PATH
});

const buildProgressRecordShare = (book) => {
  if (!book) {
    return buildProgressToolShare();
  }
  return buildAppShare({
    title: `${book.title || '好书'} · 阅读进度`,
    path: DEFAULT_SHARE_PATH
  });
};

const buildCircleShare = () => buildAppShare();

module.exports = {
  APP_SHARE_TITLE,
  DEFAULT_SHARE_PATH,
  enableWechatShareMenu,
  buildAppShare,
  buildHomeShare,
  buildProgressToolShare,
  buildProgressRecordShare,
  buildCircleShare
};
