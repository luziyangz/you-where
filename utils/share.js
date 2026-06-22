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
  title: '邀请你一起共读书房',
  path: DEFAULT_SHARE_PATH
});

const buildBookstoreShare = () => buildAppShare({
  title: '来看看这个共读书房',
  path: '/pages/bookstore/index'
});

const buildBookDetailShare = (book, catalogId) => {
  if (!book || !catalogId) {
    return buildBookstoreShare();
  }
  return buildAppShare({
    title: `${book.title || '好书'} · 共读书房`,
    path: `/pages/book-detail/index?catalog_id=${encodeURIComponent(String(catalogId))}`
  });
};

const buildCircleShare = () => buildAppShare();

module.exports = {
  APP_SHARE_TITLE,
  DEFAULT_SHARE_PATH,
  enableWechatShareMenu,
  buildAppShare,
  buildHomeShare,
  buildBookstoreShare,
  buildBookDetailShare,
  buildCircleShare
};
