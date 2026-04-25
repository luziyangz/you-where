const LEGAL_META = {
  updatedAt: "2026-03-27",
  effectiveAt: "2026-03-27",
  contactEmail: "support@example.com",
  serviceTime: "工作日 09:30 - 18:30",
  appName: "你在哪页",
};

const PRIVACY_SECTIONS = [
  {
    id: "collect",
    title: "1. 我们收集的信息",
    content:
      "为保障基础功能运行，我们可能收集账号标识、设备基础信息、阅读进度与共读互动记录。",
  },
  {
    id: "usage",
    title: "2. 信息使用目的",
    content:
      "我们仅将信息用于登录鉴权、功能实现、服务优化与安全风控，不会将你的个人信息用于与服务无关的用途。",
  },
  {
    id: "storage",
    title: "3. 信息存储与保护",
    content:
      "我们采取合理的技术与管理措施保护数据安全，并在实现业务目的所需的最短期限内保存相关信息。",
  },
  {
    id: "share",
    title: "4. 信息共享与披露",
    content:
      "除法律法规要求或经你明确授权外，我们不会向无关第三方出售或共享你的个人信息。",
  },
  {
    id: "rights",
    title: "5. 你的权利",
    content:
      "你可以通过应用内设置或联系我们，申请查询、更正、删除相关信息，或撤回授权。",
  },
  {
    id: "contact",
    title: "6. 联系我们",
    content:
      "如对本政策有疑问，可通过“关于我们”页面提供的方式反馈，我们会尽快处理。",
  },
];

const AGREEMENT_SECTIONS = [
  {
    id: "desc",
    title: "1. 协议说明",
    content:
      "欢迎使用本应用。你在注册、登录或使用服务时，即表示你已阅读并同意本协议。",
  },
  {
    id: "service",
    title: "2. 服务内容",
    content:
      "本应用提供共读、阅读进度记录、伙伴互动等功能。具体功能以实际提供页面为准。",
  },
  {
    id: "account",
    title: "3. 账号与安全",
    content:
      "你应妥善保管账号与登录凭证，不得将账号用于违法违规行为。因个人原因导致的风险由你自行承担。",
  },
  {
    id: "behavior",
    title: "4. 用户行为规范",
    content:
      "你不得发布违法、侵权、侮辱、骚扰或其他不当内容，不得破坏系统安全与正常运行秩序。",
  },
  {
    id: "ip",
    title: "5. 知识产权",
    content:
      "应用内的产品设计、代码、商标与文案等受法律保护，未经许可不得擅自复制、传播或商用。",
  },
  {
    id: "disclaimer",
    title: "6. 免责声明",
    content:
      "在法律允许范围内，我们不对因网络中断、不可抗力或第三方原因导致的服务异常承担无限责任。",
  },
  {
    id: "update",
    title: "7. 协议更新",
    content:
      "我们可能根据业务发展调整本协议，更新后将通过页面公示。你继续使用即视为接受更新内容。",
  },
];

const ABOUT_SECTIONS = [
  {
    id: "intro",
    title: "产品简介",
    content:
      "我们是一款面向日常阅读场景的共读小程序，支持伙伴绑定、进度同步、打卡记录与共读讨论。",
  },
  {
    id: "vision",
    title: "我们的愿景",
    content:
      "希望通过轻量而稳定的产品体验，帮助用户建立长期阅读习惯，让阅读从“一个人坚持”变成“彼此陪伴”。",
  },
];

module.exports = {
  LEGAL_META,
  PRIVACY_SECTIONS,
  AGREEMENT_SECTIONS,
  ABOUT_SECTIONS,
};
