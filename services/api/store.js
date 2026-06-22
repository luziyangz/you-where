const { requestV2, makeClientRequestId } = require('./base');

const DEFAULT_V2_BASE = 'https://www.nizaina.online/api/v2';

const getV2BaseUrl = () => {
  const app = getApp();
  let baseUrl = (app && app.globalData && app.globalData.apiBaseUrl) || DEFAULT_V2_BASE;
  if (/\/api\/v1$/i.test(baseUrl)) {
    baseUrl = baseUrl.replace(/\/api\/v1$/i, '/api/v2');
  } else if (!/\/api\/v2$/i.test(baseUrl)) {
    baseUrl = `${baseUrl.replace(/\/$/, '')}/api/v2`;
  }
  return baseUrl;
};

const storeSearchBooks = (query = '', page = 1, category = 'all') => {
  const params = [
    `query=${encodeURIComponent(query || '')}`,
    `page=${page}`,
    `category=${encodeURIComponent(category || 'all')}`
  ];
  return requestV2({
    url: `/store/books?${params.join('&')}`,
    method: 'GET'
  });
};

const storeGetBook = (catalogId) => {
  return requestV2({
    url: `/store/books/${encodeURIComponent(catalogId || '')}`,
    method: 'GET'
  });
};

const storeReadPage = (catalogId, page = 1) => {
  return requestV2({
    url: `/store/books/${encodeURIComponent(catalogId || '')}/read?page=${page}`,
    method: 'GET',
    timeout: 20000
  });
};

/** 自动生成章节目录（登录），正文须已入库 */
const storeGetCatalogToc = (catalogId) => {
  return requestV2({
    url: `/store/books/${encodeURIComponent(catalogId || '')}/toc`,
    method: 'GET',
    timeout: 60000
  });
};

/** 书城正文阅读进度（登录），返回 { last_page, total_pages } */
const storeGetCatalogReadingProgress = (catalogId) => {
  return requestV2({
    url: `/store/books/${encodeURIComponent(catalogId || '')}/reading-progress`,
    method: 'GET'
  });
};

const storePutCatalogReadingProgress = (catalogId, page) => {
  return requestV2({
    url: `/store/books/${encodeURIComponent(catalogId || '')}/reading-progress`,
    method: 'PUT',
    data: { page: Number(page) || 1 }
  });
};

/** 书城摘抄 / 划重点列表（登录） */
const storeListCatalogMarks = (catalogId) => {
  return requestV2({
    url: `/store/books/${encodeURIComponent(catalogId || '')}/marks`,
    method: 'GET'
  });
};

/** 新增或更新一条摘抄（登录） */
const storeUpsertCatalogMark = (catalogId, payload) => {
  const p = payload || {};
  return requestV2({
    url: `/store/books/${encodeURIComponent(catalogId || '')}/marks`,
    method: 'PUT',
    data: {
      page: Number(p.page) || 1,
      para_index: Math.max(0, Number(p.para_index) || 0),
      style: p.style === 'underline' ? 'underline' : 'marker',
      note: String(p.note || '').slice(0, 500),
      text_snap: String(p.text_snap || '').slice(0, 512)
    }
  });
};

/** 删除摘抄（登录） */
const storeDeleteCatalogMark = (catalogId, page, paraIndex) => {
  const pg = Number(page) || 1;
  const pi = Math.max(0, Number(paraIndex) || 0);
  return requestV2({
    url: `/store/books/${encodeURIComponent(catalogId || '')}/marks?page=${pg}&para_index=${pi}`,
    method: 'DELETE'
  });
};

/** 我的书架：tab 为 favorites | recent */
const storeGetMyShelf = (tab = 'recent', page = 1) => {
  const t = tab === 'favorites' ? 'favorites' : 'recent';
  return requestV2({
    url: `/store/my-shelf?tab=${encodeURIComponent(t)}&page=${page}`,
    method: 'GET'
  });
};

const storeAddFavorite = (catalogId) => {
  return requestV2({
    url: `/store/books/${encodeURIComponent(catalogId || '')}/favorite`,
    method: 'POST'
  });
};

const storeRemoveFavorite = (catalogId) => {
  return requestV2({
    url: `/store/books/${encodeURIComponent(catalogId || '')}/favorite`,
    method: 'DELETE'
  });
};

/** 上传 TXT 全书入库（需登录），成功后返回 { catalog_id, title, total_pages } */
const storeUploadTxtBook = ({ filePath, title, author }) => {
  const token = wx.getStorageSync('token') || '';
  const baseUrl = getV2BaseUrl();
  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: `${baseUrl}/store/books/import-txt`,
      filePath,
      name: 'file',
      timeout: 120000,
      formData: {
        title: title || '未命名书目',
        author: author || ''
      },
      header: {
        Authorization: token ? `Bearer ${token}` : '',
        'X-Request-Id': makeClientRequestId()
      },
      success(res) {
        let body;
        try {
          body = typeof res.data === 'string' ? JSON.parse(res.data) : res.data;
        } catch (e) {
          reject({ code: -1, message: '响应解析失败' });
          return;
        }
        if (res.statusCode >= 200 && res.statusCode < 300 && body && body.code === 0) {
          resolve(body.data);
          return;
        }
        reject({
          code: (body && body.code) || res.statusCode,
          message: (body && body.message) || '上传失败'
        });
      },
      fail(err) {
        const errMsg = (err && err.errMsg) || '';
        const hint = /timeout/i.test(errMsg) ? '上传超时，请尝试较小文件' : '网络上传失败';
        reject({ code: -1, message: hint, detail: err });
      }
    });
  });
};

/** 添加合规在线阅读链接（仅元数据 + 占位页数，小程序内打开需复制到浏览器） */
const storeImportReadUrl = (payload) => {
  return requestV2({
    url: '/store/books/import-url',
    method: 'POST',
    data: {
      title: payload.title,
      author: payload.author || '',
      read_url: payload.read_url,
      estimated_pages: payload.estimated_pages
    }
  });
};

module.exports = {
  storeAddFavorite,
  storeDeleteCatalogMark,
  storeGetBook,
  storeGetCatalogReadingProgress,
  storeGetCatalogToc,
  storeGetMyShelf,
  storeImportReadUrl,
  storeListCatalogMarks,
  storePutCatalogReadingProgress,
  storeReadPage,
  storeRemoveFavorite,
  storeSearchBooks,
  storeUpsertCatalogMark,
  storeUploadTxtBook
};
