# 当前计划

## 计划名称
- 第十七轮：阿里云 Docker 化部署落地

## 目标
- 为 FastAPI 后端补齐 Dockerfile、Docker Compose、Nginx 网关和云端自动部署脚本。
- 支持阿里云 `47.99.240.126` 使用 `IP + 端口` 进行开发联调。
- 预留 SSL 证书配置，但不伪装未备案域名已经可作为正式小程序后端域名。
- 提供本地同步到阿里云的脚本，后续拿到 SSH 凭据后可执行远程部署。

## 可行性
- 可行。
- 当前域名 `www.nizaina.com` 未备案，在大陆云服务器上会被拦截，不能作为正式小程序访问入口。
- SSL 免费证书可用于域名 HTTPS，但不能解决 `IP + HTTPS` 的证书域名不匹配问题。
- 当前最稳妥联调入口为 `http://47.99.240.126:18080/api/v2`。

## 执行项
1. [x] 更新 `backend/Dockerfile`，使用国内 pip/apt 镜像并以非 root 用户运行后端。
2. [x] 更新 `backend/docker-compose.yml`，编排 MySQL、FastAPI 后端和 Nginx 网关。
3. [x] 新增 Nginx 配置，默认暴露 HTTP 网关，预留 SSL 配置示例。
4. [x] 新增 `backend/scripts/docker_entrypoint.sh`，容器启动时等待 MySQL 并执行表结构更新。
5. [x] 新增 `backend/scripts/cloud_deploy.sh`，云端自动安装 Docker、配置国内镜像、生成 `.env` 并部署服务。
6. [x] 新增 `backend/scripts/sync_to_aliyun.ps1` 和 `backend/scripts/sync_to_aliyun.sh`，支持本地打包上传并触发云端部署。
7. [x] 替换 `backend/deploy_guide.md`，明确部署命令、端口、安全组、SSL 限制和运维命令。
8. [x] 更新 `README.md`，增加阿里云 Docker 部署入口。
9. [x] 执行静态校验和项目回归测试。

## 验证结果
- PowerShell 同步脚本语法：通过。
- `backend/docker-compose.yml` YAML 解析：通过。
- `backend/deploy_guide.md` UTF-8 读取：通过。
- Shell 脚本 UTF-8 读取：通过。
- 部署包内容验证：通过，包含 `.env.example`、`docker-compose.yml`、`scripts/cloud_deploy.sh`。
- 前端状态脚本：`node scripts/check_frontend_state.js`，通过，输出 `frontend state check ok`。
- 后端全量回归：`pytest -q`，通过，结果 `26 passed`。
- 公网排障补充：新增 `/nginx-health`，并把云端脚本的本地健康检查和公网自检分开输出。

## 未完成项
- 当前机器未安装 Docker，无法本地执行 `docker compose config` 或真实构建镜像。
- 当前机器未安装 `bash/sh`，无法本地执行 shell 语法检查。
- 尚未拿到阿里云 SSH 用户、密码或密钥，因此未实际同步到 `47.99.240.126`。
- 需要在阿里云安全组放行 `18080/tcp`；如果启用 SSL 测试，再放行 `18443/tcp`。

## 当前状态
- 第十八轮结伴页体验修正已完成：测试账号共读码已确认，二维码显示裁切已修复，复制入口已简化。
- 第十九轮已补齐云端隐藏测试用户种子脚本，真实用户可绑定已种子的 `900001` / `900002`。
- 最新验证：`node scripts/check_frontend_state.js` 通过，`pytest -q` 为 `27 passed`。
- 云端部署仍需继续关注公网安全组/防火墙以及小程序真机扫码验收。
