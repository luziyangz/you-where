const { requestV2 } = require('./base');

const storeSearchBooks = (query = '', page = 1, category = 'all') => {
  const params = [
    `query=${encodeURIComponent(query || '')}`,
    `page=${Number(page) || 1}`,
    `category=${encodeURIComponent(category || 'all')}`
  ];
  return requestV2({
    url: `/store/books?${params.join('&')}`,
    method: 'GET'
  });
};

module.exports = {
  storeSearchBooks
};
