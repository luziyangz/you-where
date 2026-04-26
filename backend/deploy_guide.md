# 阿里云 Docker 部署指南

目标服务器：`47.99.240.126`

当前约束：

- `www.nizaina.com` 未备案，在大陆云服务器上会被拦截，当前只能使用 `IP + 端口` 做开发/联调。
- SSL 证书通常绑定域名，直接用 `https://47.99.240.126:端口` 会出现证书域名不匹配。正式小程序上线仍需要“已备案域名 + HTTPS + 微信后台 request 合法域名”。
- 本指南默认使用 `http://47.99.240.126:18080` 暴露后端网关，MySQL 不对公网开放。

## 一、部署内容

Docker Compose 会启动三个服务：

- `you_where_mysql`：MySQL 8.0，内部网络访问，数据持久化到 Docker volume。
- `you_where_backend`：FastAPI 后端，内部监听 `8000`，自动等待 MySQL 并执行表结构更新。
- `you_where_nginx`：Nginx 网关，公网暴露 `18080 -> 80`，可选 `18443 -> 443`。

部署后接口地址：

```bash
健康检查: http://47.99.240.126:18080/health
Nginx 自检: http://47.99.240.126:18080/nginx-health
API Base: http://47.99.240.126:18080/api/v2
```

## 二、阿里云安全组

在阿里云控制台放行：

```text
22/tcp      SSH
18080/tcp   当前后端 HTTP 网关
18443/tcp   可选 HTTPS 测试端口
```

不要放行 `3306/tcp`，MySQL 只应在 Docker 内网访问。

## 三、本地同步并自动部署

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

## 四、云端自动部署脚本

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
- 构建并启动 MySQL、后端、Nginx。
- 检查 `http://127.0.0.1:18080/health`。

部署后建议执行：

```bash
curl -i http://127.0.0.1:18080/nginx-health
curl -i http://127.0.0.1:18080/health
curl -i http://47.99.240.126:18080/health
```

如果 `127.0.0.1:18080/health` 正常，但公网 IP 超时，优先检查阿里云安全组和服务器系统防火墙，而不是后端容器。

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
入方向 TCP 18080  来源 0.0.0.0/0 或你的固定公网 IP/32
```

CentOS/Alibaba Cloud Linux 如果启用了 firewalld：

```bash
sudo firewall-cmd --state
sudo firewall-cmd --permanent --add-port=18080/tcp
sudo firewall-cmd --reload
```

Ubuntu 如果启用了 ufw：

```bash
sudo ufw allow 18080/tcp
sudo ufw status
```

## 五、环境变量

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
HTTP_PORT=18080
HTTPS_PORT=18443
PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
STORE_ENABLE_NETWORK=0
ENABLE_TEST_USERS=0
```

生产环境必须保持 `ENABLE_TEST_USERS=0`。

## 六、隐藏测试用户

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

## 七、SSL 证书可选配置

当前未备案域名不适合作为正式小程序后端域名。若只是预留配置，证书文件放到：

```text
backend/nginx/certs/www.nizaina.com.pem
backend/nginx/certs/www.nizaina.com.key
```

在服务器上启用示例配置：

```bash
cd /opt/you-where-backend/nginx/conf.d
sudo cp ssl.conf.example ssl.conf
sudo docker compose -f /opt/you-where-backend/docker-compose.yml restart nginx
```

启用后测试地址为：

```bash
https://www.nizaina.com:18443/health
```

注意：如果域名仍未备案或被拦截，该地址仍无法稳定访问；如果用 IP 访问 HTTPS，浏览器和小程序会因证书域名不匹配报错。

## 八、运维命令

进入服务器目录：

```bash
cd /opt/you-where-backend
```

查看状态：

```bash
sudo docker compose ps
```

查看日志：

```bash
sudo docker compose logs -f backend
sudo docker compose logs -f nginx
sudo docker compose logs -f mysql
```

重启：

```bash
sudo docker compose restart
```

更新部署：

```bash
sudo sh scripts/cloud_deploy.sh
```

备份 MySQL：

```bash
sudo docker exec you_where_mysql sh -c 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" you_where' > you_where_backup.sql
```

## 九、小程序联调配置

当前开发联调可把小程序 API Base 配置为：

```text
http://47.99.240.126:18080/api/v2
```

正式版发布前必须切换为：

```text
https://已备案域名/api/v2
```

并在微信公众平台配置 `request 合法域名`。
