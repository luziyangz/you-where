/** 绑定/解绑申请文案与展示辅助 */

const TYPE_LABEL = {
  bind: '绑定结伴',
  unbind: '解除结伴'
};

const pairRequestTitle = (req) => {
  if (!req) {
    return '';
  }
  const name = (req.other_user && req.other_user.nickname) || '对方';
  if (req.request_type === 'bind') {
    return req.direction === 'incoming' ? `${name} 请求与你绑定` : `已向 ${name} 发送绑定申请`;
  }
  if (req.request_type === 'unbind') {
    return req.direction === 'incoming' ? `${name} 请求解除结伴` : `已向 ${name} 发送解绑申请`;
  }
  return TYPE_LABEL[req.request_type] || '待处理申请';
};

const pairRequestSub = (req) => {
  if (!req) {
    return '';
  }
  const days = Number(req.expires_in_days);
  const expireHint = Number.isFinite(days) && days > 0 ? `约 ${days} 天后自动视为不同意` : '超过 7 天未处理将视为不同意';
  if (req.direction === 'outgoing') {
    return expireHint;
  }
  return `${expireHint}；同意后立即生效`;
};

const canForceUnbind = (bindDays) => Number(bindDays || 0) >= 7;

module.exports = {
  canForceUnbind,
  pairRequestSub,
  pairRequestTitle
};
