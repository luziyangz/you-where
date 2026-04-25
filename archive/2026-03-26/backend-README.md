# 你在哪页 — 后端服务

> Python FastAPI + SQLite，为"你在哪页"微信小程序提供全部后端接口。

---

## 快速启动

### 方式一：双击脚本（Windows）

```
双击 start.bat
```

脚本会自动安装依赖并启动服务。

### 方式二：命令行

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

启动后访问：
- **接口文档**：http://127.0.0.1:8000/docs
- **健康检查**：http://127.0.0.1:8000/health

---

## 环境变量

| 变量名               | 说明                        | 默认值  |
|--------------------|-----------------------------|--------|
| `WECHAT_APP_ID`    | 微信小程序 AppID              | 空（走 debug 模式） |
| `WECHAT_APP_SECRET`| 微信小程序 AppSecret          | 空（走 debug 模式） |
| `DB_BACKEND`       | 数据库后端（`sqlite`/`mysql`） | `sqlite` |
| `MYSQL_HOST`       | MySQL 主机                   | `127.0.0.1` |
| `MYSQL_PORT`       | MySQL 端口                   | `3306` |
| `MYSQL_USER`       | MySQL 用户                   | `root` |
| `MYSQL_PASSWORD`   | MySQL 密码                   | 空 |
| `MYSQL_DB`         | MySQL 数据库名               | `youzainaye` |

> 未配置微信密钥时，登录接口接受前端传入的 `debug_open_id` 作为用户唯一标识，方便本地开发调试。

> 重构期支持数据库后端切换：设置 `DB_BACKEND=mysql` 可切换到 MySQL；如需快速回滚，改回 `DB_BACKEND=sqlite` 后重启服务即可。

---

## 运行测试

```bash
cd backend
pip install pytest httpx
pytest test_app.py -v
```

---

## 小程序联调配置（`apiBaseUrl`）

小程序端已支持按环境自动切换 API 地址，并支持本地覆盖值 `apiBaseUrlOverride`。

### 场景 1：本地开发（开发者工具）

- 小程序环境：`develop`
- 默认地址：`http://127.0.0.1:8000/api/v1`
- 适用：后端与开发者工具在同一台机器

### 场景 2：局域网真机联调

- 小程序环境：通常仍是 `develop` / `trial`
- 建议方式：在小程序本地存储写入 `apiBaseUrlOverride`
- 示例地址：`http://192.168.1.23:8000/api/v1`（替换为你电脑的局域网 IP）
- 注意：需确保手机与电脑同一网络，且后端监听地址可被手机访问

### 场景 3：生产环境（发布版）

- 小程序环境：`release`
- 默认地址：在 `app.js` 的 `API_BASE_URL_BY_ENV.release` 配置
- 要求：
  - 使用 HTTPS 域名
  - 域名已在小程序后台配置为合法 request 域名

---

## 项目结构

```
backend/
├── app.py            # FastAPI 应用主文件（全量实现）
├── test_app.py       # 完整接口测试套件（pytest）
├── requirements.txt  # Python 依赖
├── start.bat         # Windows 一键启动脚本
├── README.md         # 本文件
└── data/
    └── app.db        # SQLite 数据库（运行时自动创建）
```

---

## API 概览

> v2 重构进行中：当前稳定接口仍为 `/api/v1/*`，v2 契约见  
> `docs/superpowers/specs/2026-03-23-fastapi-mysql-v2-contract.md`

### 认证

| 方法   | 路径                             | 说明                           |
|--------|----------------------------------|-------------------------------|
| POST   | `/api/v1/auth/login`             | 微信登录（或本地 debug 模式）    |
| POST   | `/api/v1/auth/accept-agreement`  | 接受用户协议                    |

### 用户

| 方法   | 路径               | 说明                              |
|--------|--------------------|----------------------------------|
| GET    | `/api/v1/me`       | 获取当前用户信息（含 `join_days`） |
| GET    | `/api/v1/me/stats` | 获取统计（已读本数/总页数/笔记数/共读天数） |

### 首页

| 方法   | 路径           | 说明                          |
|--------|----------------|------------------------------|
| GET    | `/api/v1/home` | 首页聚合（user + pair + book）|

### 共读关系

| 方法   | 路径                    | 说明                        |
|--------|-------------------------|-----------------------------|
| GET    | `/api/v1/pair/current`  | 获取当前共读关系（含统计）   |
| POST   | `/api/v1/pair/bind`     | 绑定伙伴（通过 6 位共读码）  |
| POST   | `/api/v1/pair/unbind`   | 解绑伙伴                     |

### 书籍

| 方法   | 路径                    | 说明                    |
|--------|-------------------------|-------------------------|
| POST   | `/api/v1/books`         | 添加共读书籍             |
| GET    | `/api/v1/books/current` | 获取当前共读书（含进度） |
| GET    | `/api/v1/books`         | 书籍列表（可按 status 过滤） |

### 阅读记录

| 方法   | 路径                                  | 说明                     |
|--------|---------------------------------------|--------------------------|
| POST   | `/api/v1/entries`                     | 提交阅读进度/笔记（幂等） |
| GET    | `/api/v1/books/{book_id}/entries`     | 获取笔记列表（含锁定状态）|
| POST   | `/api/v1/entries/{entry_id}/replies`  | 回复笔记                  |

---

## 统一响应格式

```json
{
  "code": 0,
  "message": "ok",
  "data": {},
  "request_id": "20260323120000-abcdef"
}
```

- `code = 0`：成功
- `code = 4xxxx`：客户端错误（参数/权限）
- `code = 5xxxx`：服务端错误

---

## 测试命名约定（重构期）

- `test_v2_*`：v2 契约与行为测试
- `test_v1_compat_*`：v1 兼容壳测试
- `test_migration_*`：SQLite -> MySQL 迁移验证测试

---

## 核心业务逻辑

### 进度锁（防剧透）

拉取笔记时，若伙伴的笔记页码 > 我的当前最大进度，该笔记的 `is_locked = true`，`note_content` 返回 `null`。只有当你阅读到对应页码后，笔记才会自动解锁。

### 自动归档

当双方都达到书籍总页数时，书籍状态自动从 `reading` 改为 `finished`。

### 幂等提交

`POST /api/v1/entries` 支持 `client_request_id` 字段。网络重试时传入相同 ID，服务端会识别并返回之前的结果，不会重复创建记录。

### 性能优化

- SQLite WAL 模式（高并发读写）
- 8 个覆盖索引（热点查询路径）
- 连接级缓存（10000 页）
- 内存限流（登录接口：每 IP 每分钟 20 次）
- 结构化请求日志（路径、状态码、耗时）
