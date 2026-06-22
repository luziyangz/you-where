/**
 * 阅读进度本地缓存与 readerResume 对齐，避免各入口页码不一致
 */

const RESUME_PREFIX = 'readerResume:';
const PAGE_CACHE_INDEX_PREFIX = 'readerPageCacheIndex:';

const syncReadingProgressCache = (catalogId, page) => {
  const cid = String(catalogId || '').trim();
  const pageNum = Math.max(1, Math.floor(Number(page) || 0));
  if (!cid || !pageNum) {
    return;
  }
  const updatedAt = Date.now();
  try {
    wx.setStorageSync(`${RESUME_PREFIX}${cid}`, {
      page: pageNum,
      sliceIndex: 0,
      sliceRatio: 0,
      updatedAt
    });
    const indexKey = `${PAGE_CACHE_INDEX_PREFIX}:${cid}`;
    const rawIndex = wx.getStorageSync(indexKey) || [];
    const list = Array.isArray(rawIndex) ? rawIndex.slice() : [];
    const hit = list.find((item) => Number(item.page) === pageNum);
    if (hit) {
      hit.updatedAt = updatedAt;
    } else {
      list.push({ page: pageNum, updatedAt });
    }
    list.sort((a, b) => Number(b.updatedAt || 0) - Number(a.updatedAt || 0));
    wx.setStorageSync(indexKey, list.slice(0, 80));
  } catch (e) {
    /* 存储失败不影响阅读 */
  }
};

/** 构建阅读器 URL（续读带 page，目录跳转带 jump=1） */
const buildReaderUrl = (catalogId, options = {}) => {
  const cid = String(catalogId || '').trim();
  if (!cid) {
    return '';
  }
  const page = Math.max(0, Math.floor(Number(options.page) || 0));
  const restart = !!options.restart;
  const jump = !!options.jump;
  let url = `/pages/reader/index?catalog_id=${encodeURIComponent(cid)}`;
  if (restart) {
    url += '&restart=1';
  } else if (jump && page > 0) {
    url += `&page=${page}&jump=1`;
  } else if (page > 1) {
    url += `&page=${page}`;
  }
  return url;
};

module.exports = {
  syncReadingProgressCache,
  buildReaderUrl
};
