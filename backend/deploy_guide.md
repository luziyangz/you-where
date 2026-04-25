# 阿里云轻量应用服务器部署指南 (FastAPI + MySQL)

本指南旨在帮助您将后端服务部署到阿里云轻量应用服务器（建议使用 Ubuntu 22.04 LTS 或 CentOS 7.9+ 系统）。您可以选择**直接在 Linux 系统部署**或使用 **Docker 容器化部署**。

---

## 方案一：使用 Docker 容器化部署 (推荐)

Docker 部署方式更简单，能自动处理数据库和 Python 环境的隔离，是目前最推荐的生产环境部署方式。

### 1.1 安装 Docker
在服务器上运行以下命令：
```bash
# 安装 Docker
curl -fsSL https://get.docker.com | bash -s docker --mirror Aliyun
# 启动并设置开机自启
sudo systemctl start docker
sudo systemctl enable docker
# 安装 Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 1.2 准备配置文件
上传 `backend` 目录下的所有文件到服务器（推荐上传到 `admin` 用户的家目录，如 `/home/admin/youzainaye-backend`）。

在**本地终端**执行以下命令进行上传：
```bash
# 将整个 backend 目录上传到服务器
scp -r ./backend admin@您的服务器公网IP:/home/admin/youzainaye-backend
```

上传完成后，在服务器上创建 `.env` 文件：
```bash
cd /home/admin/youzainaye-backend
ls
nano .env
```
确保 `.env` 中的数据库配置与 `docker-compose.yml` 中的环境变量一致。

### 1.3 启动服务
```bash
# 构建并后台启动所有容器
sudo docker-compose up -d
```
Docker 会自动完成以下操作：
1. 下载并启动 MySQL 8.0 容器。
2. 自动运行 `scripts/mysql_init.sql` 进行数据库初始化。
3. 构建并启动 FastAPI 后端容器。

### 1.4 验证
访问 `http://您的服务器IP:8000/health`。

---

## 方案二：直接在 Linux 系统部署 (传统方式)

### 2.1 阿里云控制台设置
- **防火墙**: 在阿里云控制台 -> 轻量应用服务器 -> 安全 -> 防火墙中，开放以下端口：
  - `80` (HTTP)
  - `443` (HTTPS, 如果需要)
  - `3306` (MySQL, 仅当您需要从外部管理数据库时开放，建议生产环境不开放)
  - `8000` (FastAPI 默认测试端口，生产环境通常隐藏在 Nginx 后)

### 2.2 服务器环境安装
连接到服务器后，执行以下命令安装基础环境：

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装 Python 和虚拟环境
sudo apt install -y python3-pip python3-venv

# 安装 MySQL (如果服务器没自带)
sudo apt install -y mysql-server

# 安装 Nginx (用于反向代理)
sudo apt install -y nginx
```

## 3. 代码上传

将本地 `backend` 目录下的所有文件上传到服务器。建议上传到 `admin` 用户的家目录下：

```bash
# 在本地运行：
scp -r ./backend admin@您的服务器公网IP:/home/admin/youzainaye-backend
```

---

## 方案三：域名解析与小程序上线 (打通最后一步)

要让小程序能正式访问云服务器，必须满足：**已备案域名 + HTTPS 证书 + 微信后台配置**。

### 3.1 域名解析 (DNS)
在阿里云域名管理后台，为您已备案的域名 `nizaina.online` 添加解析记录：
- **记录类型**: `A`
- **主机记录**: `www` (或 `@`)
- **解析线路**: 默认
- **记录值**: `47.99.240.126`

解析完成后，访问 `http://www.nizaina.online:8000/health` 应能看到结果。

### 3.2 申请 SSL 证书 (开启 HTTPS)
微信小程序**强制要求**使用 HTTPS 协议（443 端口）。
1. 在阿里云控制台搜索“数字证书管理服务”。
2. 申请“免费证书”（每个账号通常有 20 个额度）。
3. 证书签发后，下载 **Nginx** 格式的证书文件（包含 `.pem` 和 `.key`）。

### 3.3 配置 Nginx 反向代理
在服务器上安装并配置 Nginx，将 HTTPS 请求转发到 Docker 容器的 8000 端口。

```nginx
# /etc/nginx/sites-available/default 示例配置
server {
    listen 443 ssl;
    server_name www.nizaina.online;

    ssl_certificate /etc/nginx/cert/www.nizaina.online.pem;
    ssl_certificate_key /etc/nginx/cert/www.nizaina.online.key;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 3.4 微信小程序后台配置
1. 登录 [微信公众平台](https://mp.weixin.qq.com/)。
2. 进入 **开发** -> **开发管理** -> **开发设置**。
3. 找到 **服务器域名**，在 `request合法域名` 中添加：
   `https://www.nizaina.online`

### 3.5 验证上线
在小程序代码中，将 API 请求地址改为：
`https://www.nizaina.online/your-api-endpoint`
pip install --upgrade pip
pip install -r requirements.txt
```

## 5. 数据库配置

### 5.1 创建数据库
```bash
sudo mysql -u root -p
```
在 MySQL 终端中执行：
```sql
CREATE DATABASE youzainaye CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- 创建专门的数据库用户（推荐）
CREATE USER 'youzainaye_user'@'localhost' IDENTIFIED BY '您的强密码';
GRANT ALL PRIVILEGES ON youzainaye.* TO 'youzainaye_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 5.2 初始化表结构
修改 `.env` 文件（参照 `.env.example`）：
```bash
cp .env.example .env
nano .env
```
填写刚才创建的数据库信息。然后运行初始化脚本：
```bash
python scripts/init_mysql_schema.py
```

## 6. 进程管理 (使用 Systemd)

创建一个 systemd 服务文件，确保服务在崩溃或重启后自动运行。

```bash
sudo nano /etc/systemd/system/youzainaye.service
```

填入以下内容：
```ini
[Unit]
Description=YouZaiNaYe FastAPI Backend
After=network.target

[Service]
User=root
Group=www-data
WorkingDirectory=/var/www/youzainaye-backend
Environment="PATH=/var/www/youzainaye-backend/venv/bin"
ExecStart=/var/www/youzainaye-backend/venv/bin/uvicorn app_main:app --host 0.0.0.0 --port 8000

[Install]
WantedBy=multi-user.target
```

启动并使服务开机自启：
```bash
sudo systemctl daemon-reload
sudo systemctl start youzainaye
sudo systemctl enable youzainaye
```

## 7. Nginx 反向代理

配置 Nginx 将 80 端口流量转发到 FastAPI。

```bash
sudo nano /etc/nginx/sites-available/youzainaye
```

填入内容：
```nginx
server {
    listen 80;
    server_name 您的域名或服务器IP;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

启用配置并重启 Nginx：
```bash
sudo ln -s /etc/nginx/sites-available/youzainaye /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 8. 验证
访问 `http://您的服务器IP/health`，如果返回 `{"status": "ok"}`，则部署成功！

## 9. 上线前测试环境校验

在正式上线前，建议按以下顺序执行：

1. 回归测试
```bash
cd backend
pytest test_v2_core_reading.py test_v2_store_reading.py test_v2_e2e_flow.py test_v2_profile.py -q
```

2. 并发压测（k6）
```bash
cd backend
set BASE_URL=https://www.nizaina.online/api/v2
set BOOK_ID=<your_book_id>
set TOKEN=<jwt_token>
k6 run scripts/loadtest_entries.js
```

3. 安全冒烟
- 未登录访问受保护接口应返回 `401`。
- 无效 Token 访问写接口应返回 `401`。

详细步骤请参考：`scripts/test_env_guide.md`。
