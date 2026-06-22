const { requestV2 } = require('./base');

const bindPair = (joinCode) => {
  return requestV2({
    url: '/pairs',
    method: 'POST',
    data: {
      join_code: joinCode
    }
  });
};

const unbindPair = (options = {}) => {
  const force = !!(options && options.force);
  return requestV2({
    url: force ? '/pairs/current?force=true' : '/pairs/current',
    method: 'DELETE'
  });
};

const respondPairRequest = (requestId, action) => {
  return requestV2({
    url: `/pairs/requests/${encodeURIComponent(requestId || '')}/respond`,
    method: 'POST',
    data: { action }
  });
};

const fetchCurrentPair = () => {
  return requestV2({
    url: '/pairs/current',
    method: 'GET'
  });
};

module.exports = {
  bindPair,
  fetchCurrentPair,
  respondPairRequest,
  unbindPair
};
