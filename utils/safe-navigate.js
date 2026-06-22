/**
 * 防止连续 navigateTo 堆叠同页导致卡顿/无响应
 */

const navigateTo = (url, ctx) => {
  const host = ctx || {};
  if (!url || host._pageNavLock) {
    return false;
  }
  host._pageNavLock = true;
  wx.navigateTo({
    url,
    complete: () => {
      host._pageNavLock = false;
    },
    fail: () => {
      host._pageNavLock = false;
    }
  });
  return true;
};

module.exports = {
  navigateTo
};
