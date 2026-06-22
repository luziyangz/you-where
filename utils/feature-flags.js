const FEATURE_FLAGS = {
  socialSharing: false
};

const isSocialSharingEnabled = () => !!FEATURE_FLAGS.socialSharing;

module.exports = {
  FEATURE_FLAGS,
  isSocialSharingEnabled
};
