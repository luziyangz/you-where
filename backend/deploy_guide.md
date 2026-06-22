# 阿里云 Docker 部署指南

目标服务器：`47.99.240.126`

当前生产入口：

- API 域名：`www.nizaina.online`
- API Base：`https://www.nizaina.online/api/v2`
- SSL 证书文件名：`www.nizaina.online.pem`、`www.nizaina.online.key`
- Docker 网关默认暴露 `80 -> 80`、`443 -> 443`，MySQL 不对公网开放。

上线前必须确保：

- 域名已备案，且 DNS `A` 记录指向服务器公网 IP `47.99.240.126`。
- 阿里云安全组放行 `80/tcp`、`443/tcp`、`22/tcp`。
- 微信公众平台已配置 request 合法域名：`https://www.nizaina.online`。

## 一、部署内容

Docker Compose 会启动三个服务：

- `you_where_mysql`：MySQL 8.0，内部网络访问，数据持久化到 Docker volume。
- `you_where_backend`：FastAPI 后端，内部监听 `8000`，自动等待 MySQL 并执行表结构更新。
- `you_where_nginx`：Nginx 网关，公网暴露 `80 -> 80`、`443 -> 443`。

部署后接口地址：

```bash
健康检查: https://www.nizaina.online/health
Nginx 自检: https://www.nizaina.online/nginx-health
API Base: https://www.nizaina.online/api/v2
```

## 二、阿里云安全组

在阿里云控制台放行：

```text
22/tcp      SSH
80/tcp      HTTP，用于跳转 HTTPS 和健康检查
443/tcp     HTTPS API 网关
```

不要放行 `3306/tcp`，MySQL 只应在 Docker 内网访问。如果服务器系统防火墙启用，也需要同步放行 `80/tcp` 和 `443/tcp`。

## 三、证书放置

把阿里云下载的 Nginx 证书解压后，放到本地：

```text
backend/nginx/certs/www.nizaina.online.pem
backend/nginx/certs/www.nizaina.online.key
```

`backend/nginx/certs/*` 已被 `.gitignore` 排除，不会提交到仓库；同步部署脚本会把证书随部署包上传到服务器。

## 四、本地同步并自动部署

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File backend\scripts\sync_to_aliyun.ps1 `
  -Server 47.99.240.126 `
  -User root `
  -Port 22 `
  -KeyPath C:\path\to\id_rsa `
  -RemoteDir /opt/you-where-backend
```

如果服务器使用密码登录，去掉 `-KeyPath`，命令会进入 SSH 密码输入流程：

```powershell
powershell -ExecutionPolicy Bypass -File backend\scripts\sync_to_aliyun.ps1 -User root
```

Linux/macOS：

```bash
SERVER=47.99.240.126 USER_NAME=root KEY_PATH=~/.ssh/id_rsa sh backend/scripts/sync_to_aliyun.sh
```

同步脚本会：

- 打包 `backend` 目录，排除 `.env`、本地数据库、缓存和日志。
- 上传到服务器 `/tmp/you-where-backend.tar.gz`。
- 解压到 `/opt/you-where-backend`。
- 在云端执行 `sudo sh scripts/cloud_deploy.sh`。

部署完成后，从本地验证：

```powershell
curl.exe -i https://www.nizaina.online/health
curl.exe -i https://www.nizaina.online/nginx-health
```

## 五、云端自动部署脚本

如果已经手动把 `backend` 目录放到服务器，可直接在服务器执行：

```bash
cd /opt/you-where-backend
sudo sh scripts/cloud_deploy.sh
```

如果服务器上已经有稳定运行的 Docker 环境，并且不希望脚本重写 `/etc/docker/daemon.json` 或重启 Docker，可执行：

```bash
cd /opt/you-where-backend
sudo env CONFIGURE_DOCKER_MIRRORS=0 sh scripts/cloud_deploy.sh
```

脚本会自动完成：

- 安装基础工具。
- 安装 Docker，并优先使用阿里云安装镜像。
- 默认配置 Docker 国内镜像源；如设置 `CONFIGURE_DOCKER_MIRRORS=0` 则跳过。
- 首次部署时自动生成 `.env` 和 MySQL 强密码。
- 检测到 `nginx/certs/www.nizaina.online.pem` 和 `nginx/certs/www.nizaina.online.key` 后自动启用 HTTPS。
- 构建并启动 MySQL、后端、Nginx。
- 检查 `http://127.0.0.1/health` 和 `https://www.nizaina.online/health`。

部署后建议执行：

```bash
curl -i http://127.0.0.1/nginx-health
curl -i http://127.0.0.1/health
curl -i https://www.nizaina.online/health
```

如果 `127.0.0.1/health` 正常，但公网域名超时，优先检查 DNS、备案状态、阿里云安全组和服务器系统防火墙，而不是后端容器。

如果公网返回 `502 Bad Gateway`，先区分是 Nginx 可达但后端不可达，还是公网入口不可达：

```bash
curl -i http://127.0.0.1:18080/nginx-health
curl -i http://127.0.0.1:18080/health
sudo docker logs -f you_where_nginx
sudo docker logs you_where_nginx --tail=100
sudo docker logs you_where_backend --tail=100
sudo docker exec you_where_nginx wget -S -O- http://backend:8000/health
```

安全组建议：

```text
入方向 TCP 80   来源 0.0.0.0/0
入方向 TCP 443  来源 0.0.0.0/0
```

CentOS/Alibaba Cloud Linux 如果启用了 firewalld：

```bash
sudo firewall-cmd --state
sudo firewall-cmd --permanent --add-port=80/tcp
sudo firewall-cmd --permanent --add-port=443/tcp
sudo firewall-cmd --reload
```

Ubuntu 如果启用了 ufw：

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw status
```

## 六、环境变量

首次云端部署会自动创建 `.env`。如需手动配置，可参考 `.env.example`：

```bash
cd /opt/you-where-backend
sudo cp .env.example .env
sudo nano .env
```

关键项：

```env
DB_BACKEND=mysql
MYSQL_ROOT_PASSWORD=replace_with_a_strong_root_password
MYSQL_USER=you_where
MYSQL_PASSWORD=replace_with_a_strong_app_password
MYSQL_DB=you_where
HTTP_PORT=80
HTTPS_PORT=443
SERVER_DOMAIN=www.nizaina.online
WECHAT_APP_ID=wx401cfbd2f9e9c978
WECHAT_APP_SECRET=replace_with_wechat_app_secret
PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
STORE_ENABLE_NETWORK=1
ENABLE_TEST_USERS=0
ENABLE_REVIEW_LOGIN=1
WECHAT_REVIEW_ACCOUNT=reviewer
WECHAT_REVIEW_PASSWORD=replace_with_review_password
```

生产环境必须保持 `ENABLE_TEST_USERS=0`。
`WECHAT_APP_ID` 必须和小程序项目 `project.config.json` 里的 `appid` 一致；当前项目 AppID 是 `wx401cfbd2f9e9c978`。如果服务器配置了其他 AppID 或错误的 AppSecret，微信登录会在 `/auth/login` 返回 `invalid code`。
`ENABLE_REVIEW_LOGIN=1` 用于微信审核账号密码登录，账号密码仅供提审填写；前端只在开发版/体验版展示该入口，正式版隐藏。

如果服务器上已有旧 `.env`，需要确认其中端口已改为：

```env
HTTP_PORT=80
HTTPS_PORT=443
SERVER_DOMAIN=www.nizaina.online
```

## 六点五、书城公版全书入库

书城「站内全书」来自 Project Gutenberg 公版中文（`pg_*` 书目）。采用 **双轨扩充**：

1. **精选清单**：`data/public_domain_books.json`（约 130 本核心中文公版，部署即入库）
2. **Gutendex 全量**：`languages=zh` 元数据同步（需外网，可覆盖更多中文书目）

容器启动时会：

1. `seed_store_books.py` 写入书目元数据  
2. `prefetch_catalog_contents.py` 从 Gutenberg 拉取全文到 `catalog_contents`（已缓存则跳过）
3. 若 `STORE_ENABLE_NETWORK=1`，后台执行 `sync_gutendex_zh_catalog.py` 同步 Gutendex 中文书目

环境变量：

```env
STORE_PREFETCH_CONTENT=1
STORE_ENABLE_NETWORK=1
GUTENDEX_FETCH_TIMEOUT=20
GUTENDEX_ZH_SYNC_MAX_PAGES=30
```

首次部署会在 **后台** 预取正文（不阻塞 API 启动）。查看进度：

```bash
sudo docker compose exec backend tail -f /app/logs/catalog_prefetch.log
sudo docker compose exec backend tail -f /app/logs/gutendex_zh_sync.log
```

> `tail -f` 在预取**已结束**后会一直等待新日志，看起来像「卡住」属正常；按 `Ctrl+C` 退出即可。若日志里已是 `共 0`，说明没有待预取书目（见下方排查）。

**预取 `共 0` 排查**（正常应约为 130 本 `pg_*`）：

```bash
# 1) 镜像内是否有公版清单（缺文件则 total 恒为 0）
sudo docker compose exec backend ls -la /app/data/
sudo docker compose exec backend python -c "from service.store_service import PUBLIC_DOMAIN_CATALOG_BOOKS as b; print('pg_books', len(b))"

# 2) 库内书目数量
sudo docker compose exec backend python -c "from common.db import SessionLocal; from repo import store_repo; db=SessionLocal(); print('catalog_ids', len(store_repo.list_catalog_ids(db))); db.close()"
```

若 `pg_books 0` 且 `/app/data/` 为空：旧版 `.dockerignore` 曾排除整个 `data/`，需**重新 build 镜像**后再 seed / prefetch。`Seed inserted: 0` 单独出现可能是书目已存在，不必惊慌；与 `共 0` 同时出现才需处理。

手动补全或重试：

```bash
cd /opt/you-where-backend
sudo docker compose exec backend python scripts/prefetch_catalog_contents.py
sudo docker compose exec backend python scripts/prefetch_catalog_contents.py --catalog-id pg_23835
sudo docker compose exec backend python scripts/sync_gutendex_zh_catalog.py --max-pages 50 --force
```

确认列类型与正文长度（需 `LONGTEXT`），以及增量索引（如 `idx_feed_posts_book_title`）：

```bash
cd /opt/you-where-backend
# 推荐：在容器内执行（宿主机无需安装 Python 依赖）
sudo docker compose exec backend python scripts/apply_schema_updates.py
# 或一键包装脚本
sudo sh scripts/apply_schema.sh
```

> **勿在宿主机直接运行** `python scripts/apply_schema_updates.py`，会报 `ModuleNotFoundError: No module named 'sqlalchemy'`。依赖仅安装在 `backend` 镜像内；容器 **entrypoint 启动时已自动执行** schema 同步，上述命令用于发版后人工确认。

全新 MySQL 空库也可直接执行 `scripts/mysql_init.sql`（22 表，与 `common/models.py` 对齐）。表结构说明见仓库根目录 `team/database-schema.md`。

若历史数据存在「误标 finished」的共读书（换书前旧逻辑），可修正为 `switched`：

```bash
sudo docker compose exec backend python scripts/repair_mislabeled_finished_books.py --dry-run
sudo docker compose exec backend python scripts/repair_mislabeled_finished_books.py
```

`catalog_manifest.json` 仅导入「共读推荐」元数据（活着、三体等版权书），**不含站内全文**；公版四大名著等请使用 `pg_*` 书目。

## 七、隐藏测试用户

测试用户不会出现在小程序界面。如需在云端开发环境使用固定共读码做绑定测试，先显式写入真实 `users` 表：

```bash
cd /opt/you-where-backend
sudo docker compose exec backend python scripts/seed_test_users.py
```

固定共读码：

```text
测试用户 A: 900001
测试用户 B: 900002
```

如果测试用户已被绑定，想重复测试绑定流程，可重置测试用户相关活跃关系：

```bash
sudo docker compose exec backend python scripts/seed_test_users.py --reset-active-pairs
```

如果希望每次容器启动都自动补齐测试用户，可在 `.env` 中设置：

```env
SEED_TEST_USERS=1
```

注意：`SEED_TEST_USERS=1` 只负责写入隐藏测试用户；`ENABLE_TEST_USERS=1` 会开启 `/api/v2/auth/test-login` 接口。云端开发一般只需要执行种子脚本，不建议开启 `ENABLE_TEST_USERS`。

## 八、运维命令

进入服务器目录：

```bash
cd /opt/you-where-backend
```

常用：

```bash
sudo docker compose ps
sudo docker compose logs -f backend
sudo docker compose logs -f nginx
sudo docker compose logs -f mysql
sudo docker compose restart
sudo docker compose exec backend python scripts/apply_schema_updates.py
sudo sh scripts/apply_schema.sh
```

### 常见错误：宿主机运行 schema 脚本

```text
ModuleNotFoundError: No module named 'sqlalchemy'
```

**原因**：在 ECS 宿主机直接执行了 `python scripts/apply_schema_updates.py`，未进入 Docker 容器。

**解决**：

```bash
sudo docker compose exec backend python scripts/apply_schema_updates.py
```

发版后若需确认 `book_title` 等新索引，重启 backend 也会触发 entrypoint 自动同步：

```bash
sudo docker compose up -d --build backend
```

### nginx 一直是 Created、未运行

常见原因：旧版 entrypoint 在启动 API 前同步预取全书，backend 长时间不健康，nginx 因 `depends_on: service_healthy` 不会启动。

处理步骤：

```bash
cd /opt/you-where-backend
# 1. 确认 80/443 未被占用
sudo ss -tlnp | grep -E ':80|:443'
# 2. 拉取最新代码并重建 backend 后，启动 nginx
sudo docker compose up -d --build backend
sudo docker compose up -d nginx
sudo docker compose ps
sudo docker logs --tail 50 you_where_nginx
```

若端口冲突，在 `.env` 中改 `HTTP_PORT`/`HTTPS_PORT` 后重新 `docker compose up -d`。

更新部署：

```bash
sudo sh scripts/cloud_deploy.sh
```

备份 MySQL：

```bash
sudo docker exec you_where_mysql sh -c 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" you_where' > you_where_backup.sql
```

## 九、数据库安全与结构同步

- 说明文档：`team/database-security.md`
- 工具：`common/db_safety.py`（LIKE 转义、破坏性操作防护、schema 校验）
- 发版后在 **backend 容器内** 执行 schema 同步并确认 `Schema sync check: OK`：

```bash
sudo docker compose exec backend python scripts/apply_schema_updates.py
# 或
sudo sh scripts/apply_schema.sh
```

不要在 ECS 宿主机直接 `python scripts/apply_schema_updates.py`（缺少 sqlalchemy）。

## 十、MySQL 集成回归（22 张业务表）

本地或 CI 使用独立测试库（端口 **3307**，库名 `you_where_test`）：

```powershell
cd backend
docker compose -f docker-compose.test.yml up -d
# 等待健康后
$env:MYSQL_TEST_PORT = "3307"
python -m pytest tests_mysql/ -v --tb=short
```

或使用脚本：

```powershell
.\scripts\run_mysql_regression.ps1
```

分阶段 k6 压测（需先启动 API 并 `ENABLE_TEST_USERS=1`）：

```powershell
python scripts/prepare_loadtest_env.py --base http://127.0.0.1:8000/api/v2
# 按脚本输出的 export 设置环境变量后
.\scripts\run_loadtest_all.ps1
```

详细 rollout 见 `team/mysql-rollout-plan.md`。

## 十一、小程序联调配置

小程序当前已默认使用：

```text
https://www.nizaina.online/api/v2
```

发布前确认微信公众平台 `开发管理 -> 开发设置 -> 服务器域名 -> request 合法域名` 已包含：

```text
https://www.nizaina.online
```
