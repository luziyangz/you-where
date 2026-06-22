const { requestV2 } = require('./base');
const { isSocialSharingEnabled } = require('../../utils/feature-flags');

const rejectWhenDisabled = () => {
  if (isSocialSharingEnabled()) {
    return null;
  }
  return Promise.reject({ code: 'SOCIAL_SHARING_DISABLED', message: '该功能暂不可用' });
};

const fetchMyFeedPosts = (page = 1, pageSize = 20) => {
  const disabled = rejectWhenDisabled();
  if (disabled) {
    return disabled;
  }
  const safePage = Number(page) > 0 ? Number(page) : 1;
  const safeSize = Number(pageSize) > 0 ? Number(pageSize) : 20;
  return requestV2({
    url: `/feed/posts/mine?page=${safePage}&page_size=${safeSize}`,
    method: 'GET'
  });
};

const fetchExploreFeedPosts = (page = 1, pageSize = 20, book = '') => {
  const disabled = rejectWhenDisabled();
  if (disabled) {
    return disabled;
  }
  const safePage = Number(page) > 0 ? Number(page) : 1;
  const safeSize = Number(pageSize) > 0 ? Number(pageSize) : 20;
  const q = (book || '').trim();
  const bookQuery = q ? `&book=${encodeURIComponent(q)}` : '';
  return requestV2({
    url: `/feed/posts/explore?page=${safePage}&page_size=${safeSize}${bookQuery}`,
    method: 'GET'
  });
};

const fetchFeedPost = (postId) => {
  const disabled = rejectWhenDisabled();
  if (disabled) {
    return disabled;
  }
  return requestV2({
    url: `/feed/posts/${encodeURIComponent(postId)}`,
    method: 'GET'
  });
};

const publishEntryToFeed = (entryId, payload) => {
  const disabled = rejectWhenDisabled();
  if (disabled) {
    return disabled;
  }
  return requestV2({
    url: `/entries/${encodeURIComponent(entryId)}/publish-to-feed`,
    method: 'POST',
    data: payload
  });
};

const deleteFeedPost = (postId) => {
  const disabled = rejectWhenDisabled();
  if (disabled) {
    return disabled;
  }
  return requestV2({
    url: `/feed/posts/${encodeURIComponent(postId)}`,
    method: 'DELETE'
  });
};

module.exports = {
  deleteFeedPost,
  fetchExploreFeedPosts,
  fetchFeedPost,
  fetchMyFeedPosts,
  publishEntryToFeed
};
