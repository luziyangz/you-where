const { requestV2 } = require('./base');

const acceptAgreement = () => {
  return requestV2({
    url: '/auth/accept-agreement',
    method: 'POST',
    data: {
      accepted: true
    }
  });
};

module.exports = {
  acceptAgreement
};
