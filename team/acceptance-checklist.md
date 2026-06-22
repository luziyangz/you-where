# 全栈验收清单

> 覆盖：Tab 四页 + 阅读主链 + 其余功能。  
> 自动化：`node scripts/check_frontend_state.js`；MySQL 回归 `pytest tests_mysql/`；Feed 单独 `pytest test_v2_feed.py`。

## 一、部署与基础设施

| # | 项 | 操作 | 期望 | 自动化 |
|---|-----|------|------|--------|
| D1 | 容器健康 | `docker compose ps` | mysql/backend/nginx 均 healthy | — |
| D2 | 健康探针 | `curl https://域名/health` | `{"status":"ok"}` | — |
| D3 | Schema 同步 | `docker compose exec backend python scripts/apply_schema_updates.py` | `Schema sync check: OK`；含 `idx_feed_posts_book_title` | `tests_mysql/test_phase0_schema.py` |
| D4 | 勿宿主机跑 schema | 宿主机 `python scripts/apply_schema_updates.py` | 应提示用 docker exec 或 `apply_schema.sh` | — |
| D5 | API 基址 | 小程序 `utils/request.js` 默认 | `https://www.nizaina.online/api/v2` | `check_frontend_state.js` |

---

## 二、Tab 四页

### 2.1 共读（`pages/home/index`）

| # | 功能 | 操作 | 期望 | 后端 |
|---|------|------|------|------|
| H1 | 未登录 | 打开小程序 | 登录引导；Tab 门禁仅首页 | `auth-gate` |
| H2 | 微信/手机号登录 | 完成登录 | token 写入；跳转正常 | `POST /auth/login`、`/auth/phone-login` |
| H3 | 首页状态 | 登录后进首页 | 显示双人状态、当前书、CTA | `GET /home` |
| H4 | 继续阅读 | 点「继续阅读」 | 进阅读器或详情 | `/store/.../read` |
| H5 | 我们的记录 | 点 CTA / Tab | 进 progress | — |
| H6 | 书友书摘入口 | 点「书友书摘」 | 进 circle explore | `GET /feed/posts/explore` |

### 2.2 书房（`pages/bookstore/index`）

| # | 功能 | 操作 | 期望 | 后端 |
|---|------|------|------|------|
| B1 | 分类列表 | 切换分类 | 分页正确、无重复偏移 | `GET /store/books` |
| B2 | 搜索 | 输入书名搜索 | 结果匹配 | `query=` |
| B3 | 进详情 | 点书目卡片 | book-detail 展示元数据 | `GET /store/books/{id}` |
| B4 | 站内全书 | 点 pg_* 公版书 | `has_text` 为真时可阅读 | `catalog_contents` |

### 2.3 我们的记录（`pages/progress/index`）

| # | 功能 | 操作 | 期望 | 后端 |
|---|------|------|------|------|
| P1 | 无共读书 | 未建书 | 空状态引导 | `GET /home` |
| P2 | 情感时间线 | 有记录 | 按时间展示 entry + reply | `GET /books/{id}/entries` |
| P3 | 标记已读 | 点未读 | 未读态清除 | `PUT /books/{id}/read-mark` |
| P4 | 回复 | 对 partner 记录回复 | 时间线出现 reply | `POST /entries/{id}/replies` |
| P5 | 补记 | 新增记录 | 出现在时间线 | `POST /books/{id}/entries` |
| P6 | 分享摘录 | 选一条 → 确认 → 发布 | 「已生成分享」；可进 circle | `POST /entries/{id}/publish-to-feed` |
| P7 | 书友书摘入口 | 点卡片 | 进 circle | — |

### 2.4 我的（`pages/profile/index`）

| # | 功能 | 操作 | 期望 | 后端 |
|---|------|------|------|------|
| M1 | 资料展示 | 进个人页 | 昵称/头像/统计 | `GET /users/me/profile`、`/stats` |
| M2 | 改昵称 | 编辑保存 | 刷新后生效 | `PUT /users/me` |
| M3 | 阅读目标进度 | 查看卡片 | 周期进度正确 | `GET /users/me/reading-goal` |
| M4 | 共读摘录 | 点「共读摘录」 | 进 circle | — |
| M5 | 子页跳转 | 历史/目标/提醒/设置/伙伴 | 各页可打开 | 见第三节 |

---

## 三、阅读主链

```text
bookstore → book-detail → [加入共读 POST /books] → reader → [同步进度 POST /entries] → progress 时间线
```

| # | 步骤 | 操作 | 期望 | 自动化 |
|---|------|------|------|--------|
| R1 | 浏览 | 书房选书 | 详情页信息完整 | `test_v2_store_reading.py` |
| R2 | 加入共读 | 点「加入共读」 | 创建 pair 书；home 可见 | `tests_mysql/test_phase3_reading.py` |
| R3 | 阅读器分页 | 翻页 | 正文加载；进度记忆 | `GET /store/books/{id}/read` |
| R4 | 阅读器同步 | 退出或同步 | progress 可见新页记录 | `POST /books/{id}/entries` |
| R5 | 换书请求 | partner 发起换书 | 对方可同意/拒绝 | `tests_mysql/test_phase2_pair.py` |
| R6 | 解绑 | partner 解绑 | 关系清除 | `tests_mysql/test_phase2_unbind.py` |

---

## 四、共读摘录（二期）

| # | 功能 | 操作 | 期望 | 自动化 |
|---|------|------|------|--------|
| F1 | 书友书摘 | circle Tab「书友书摘」 | 只读他人分享；无评论按钮 | `test_explore_*` |
| F2 | 书名搜索 | explore 搜索框 | 按书名过滤 | `test_v2_feed.py` |
| F3 | 我的分享 | Tab「我的分享」 | 仅本人；可删除、微信转发 | `test_phase6_feed.py` |
| F4 | onShow 刷新 | 发布后进 circle?tab=mine | 列表含新分享（静默刷新） | 手工 |
| F5 | 分享链接 | 微信打开 `?post_id=` | 预览卡片展示 | `GET /feed/posts/{id}` |
| F6 | 删除分享 | 删除后 | 链接 404；explore 不可见 | feed tests |

---

## 五、其他功能页

| 页面 | 关键验收 | 后端 | 自动化 |
|------|----------|------|--------|
| `partner` | 绑定/解绑、共读码、扫码 | `/pairs/*` | `test_phase2_pair.py` |
| `reading-history` | 分页历史 | `/users/me/reading-history` | `test_phase5_settings.py` |
| `reading-goal` | 设目标、保存 | `PUT /users/me/reading-goal` | 同上 |
| `reminder` | 读配置、保存、订阅入口 | `/users/me/reminder-config` | 同上 |
| `settings` | 跳转协议/隐私/关于 | — | 静态 |
| `privacy-policy` / `user-agreement` | 含 UGC 分享说明 | — | 手工 |
| `privacy-authorize` | 微信隐私授权 | — | 真机 |
| `about-us` | 静态展示 | — | — |
| `login-consent-panel` | 登录前协议勾选 | `accept-agreement` | 手工 |

---

## 六、认证与安全

| # | 项 | 期望 |
|---|-----|------|
| A1 | 未登录调业务 API | 401 + 回首页 |
| A2 | Tab 门禁 | 未登录不能 switchTab 到非首页 |
| A3 | 只能删自己的 feed | 403 |
| A4 | 只能分享自己的 entry | 403 |
| A5 | explore LIKE 搜索 | 特殊字符不注入 | `test_db_safety.py` |

---

## 七、回归命令（本地/CI）

```bash
# 前端静态检查
node scripts/check_frontend_state.js

# MySQL 集成（15 项，含 feed）
cd backend
python -m pytest tests_mysql/ -q

# Feed SQLite 测试（须单独跑，避免污染 MySQL 环境变量）
python -m pytest test_v2_feed.py -q

# 核心 SQLite 套件（与 feed 分开跑更稳）
python -m pytest test_v2_core_reading.py test_v2_profile.py test_v2_store_reading.py -q
```

---

## 八、云端发版后快速验收（5 分钟）

1. `sudo docker compose ps` — 全 healthy  
2. `curl -s https://www.nizaina.online/health`  
3. `sudo docker compose exec backend python scripts/apply_schema_updates.py` — OK  
4. 小程序：登录 → 书房 → 阅读一页 → 我们的记录有 entry → 分享摘录 → 书友书摘可见  
5. `sudo docker compose logs backend --tail 50` — 无持续报错  

---

## 九、已知限制（非阻断）

- 提醒真机推送依赖微信模板 + 服务器 cron，需生产单独验证  
- SQLite 多套件并行跑可能环境串扰，按第七节分开执行  
- 宿主机无 Python 依赖，运维脚本一律 `docker compose exec backend`  
