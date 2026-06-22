const { requestV2 } = require('./base');

const fetchReportReasons = () => {
  return requestV2({
    url: '/reports/reasons',
    method: 'GET'
  });
};

const submitReport = (payload) => {
  return requestV2({
    url: '/reports',
    method: 'POST',
    data: payload
  });
};

module.exports = {
  fetchReportReasons,
  submitReport
};
