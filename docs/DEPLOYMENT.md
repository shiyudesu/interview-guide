# GHCR 主动拉取部署

生产服务器不需要克隆仓库。GitHub Actions 在 `main` 分支 CI 成功后发布三个 GHCR 包：

```text
ghcr.io/<namespace>/interview-guide-backend:sha-<commit>
ghcr.io/<namespace>/interview-guide-frontend:sha-<commit>
ghcr.io/<namespace>/interview-guide-deploy:main
```

后端和前端同时发布 `main` 与不可变的 `sha-<commit>` tag。部署包的 `main` tag 最后发布，充当
已经通过 CI 的更新通道。服务器每 5 分钟主动拉取部署包，从 OCI revision 标签解析目标 commit，
再部署对应的两个 `sha-<commit>` 镜像，不直接运行移动的应用 `main` tag。

后端镜像保留 LibreOffice 文档转换能力，但只安装无图形界面组件。系统包和 Python
site-packages 分成多个较小 layer，以降低弱网络下载单个大 blob 时超时后整体失败的概率。

## 发布端准备

工作流位于 `.github/workflows/publish-ghcr.yml`，使用仓库自带的 `GITHUB_TOKEN` 发布 GHCR，
不需要配置服务器 SSH Key。首次合并到 `main` 后：

1. 等待 `CI` 工作流成功。
2. 等待 `Publish GHCR deployment` 成功。
3. 在 GitHub Packages 中确认 backend、frontend、deploy 三个包存在。

如果这些包设置为 public，服务器可以匿名拉取。如果保持 private，服务器需要一个 classic PAT：

- 至少包含 `read:packages`
- Token 所属用户必须具有对应包的读取权限
- 组织启用 SSO 时，需要为 Token 完成组织授权

服务器定时任务默认以 root 运行，因此 private 包应登录 root 的 Docker 配置：

```bash
read -rsp "GHCR token: " GHCR_TOKEN
printf '\n'
printf '%s' "$GHCR_TOKEN" | sudo docker login ghcr.io \
  --username <github-user> \
  --password-stdin
unset GHCR_TOKEN
```

## 服务器前提

支持的 Docker daemon 架构：

```text
linux/amd64
linux/arm64
```

检查环境：

```bash
docker --version
docker compose version
sudo docker info --format '{{.Architecture}}'
```

服务器只需要 Docker Engine、Compose v2、systemd、已备案域名、可用的公网 80/443，以及访问
GHCR、Docker Hub 和 Let's Encrypt 的网络，不需要 Git、Node.js、pnpm、Python、Certbot 或 uv。

安装前完成：

1. 域名 A/AAAA 记录解析到该服务器的公网地址。
2. 公网 TCP 80 和 TCP 443 可到达服务器。
3. 云安全组、主机防火墙和 NAT 转发允许上述端口。
4. 旧服务器仍提供服务时，先降低 DNS TTL；切换前不要关闭旧入口。

## 首次安装

下面以当前仓库 namespace `shiyudesu` 为例。部署包本身就是一个 OCI 镜像，可以从 GHCR 抽取，
不需要下载仓库源码：

```bash
export GHCR_NAMESPACE=shiyudesu
export DEPLOY_IMAGE="ghcr.io/${GHCR_NAMESPACE}/interview-guide-deploy:main"
export DEPLOY_TMP="$(mktemp -d)"

sudo docker pull "$DEPLOY_IMAGE"
DEPLOY_CONTAINER="$(sudo docker create "$DEPLOY_IMAGE")"
sudo docker cp "${DEPLOY_CONTAINER}:/bundle/." "$DEPLOY_TMP/"
sudo docker rm "$DEPLOY_CONTAINER"

sudo "$DEPLOY_TMP/install.sh" \
  --root /opt/interview-guide \
  --namespace "$GHCR_NAMESPACE" \
  --channel main \
  --domain interview.example.com \
  --email admin@example.com

sudo rm -rf -- "$DEPLOY_TMP"
```

### 复用服务器已有 Caddy

宿主机 Caddy 已经承载其他站点时，不要停止或卸载它。先在 `/etc/caddy/Caddyfile` 增加：

```caddyfile
interview.example.com {
    reverse_proxy 127.0.0.1:18073
}
```

校验并重载宿主机 Caddy：

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

然后在安装命令末尾增加 `--external-caddy`：

```bash
sudo "$DEPLOY_TMP/install.sh" \
  --root /opt/interview-guide \
  --namespace "$GHCR_NAMESPACE" \
  --channel main \
  --domain interview.example.com \
  --email admin@example.com \
  --external-caddy
```

该模式不会启动 Compose `gateway`，也不会占用宿主机 80/443；应用前端只监听
`127.0.0.1:18073`。证书申请、续期和 HTTP 跳转 HTTPS 全部由现有宿主机 Caddy 完成。安装和后续
主动更新会使用 `curl --resolve` 经本机 443 校验真实域名证书及 `/health`，因此宿主机需要安装
`curl`。

安装器会：

- 创建 `/opt/interview-guide/.env`
- 生成随机 PostgreSQL 和 MinIO 密码
- 写入备案域名和 ACME 联系邮箱
- 安装纯镜像 Compose、Caddy 配置和主动更新脚本
- 首次拉取并启动已经通过 CI 的不可变镜像
- 等待 Let's Encrypt 证书签发并通过真实 HTTPS `/health` 检查
- 安装并启动 `interview-guide-update.timer`

首次迁移会创建不可登录的 `legacy-owner`，用于安全承接升级前的存量资源。安装完成后创建管理员并
认领数据，密码只从交互式 TTY 读取，不写入命令参数或 `.env`：

```bash
cd /opt/interview-guide
TAG="$(sudo cat state/current-tag)"

sudo env INTERVIEW_GUIDE_IMAGE_TAG="$TAG" docker compose \
  --project-name interview-guide \
  --project-directory /opt/interview-guide \
  --env-file /opt/interview-guide/.env \
  -f /opt/interview-guide/bundle/compose.yml \
  run --rm app interview-guide-create-admin --email admin@example.com

sudo env INTERVIEW_GUIDE_IMAGE_TAG="$TAG" docker compose \
  --project-name interview-guide \
  --project-directory /opt/interview-guide \
  --env-file /opt/interview-guide/.env \
  -f /opt/interview-guide/bundle/compose.yml \
  run --rm app interview-guide-claim-legacy-data \
  --admin-email admin@example.com --yes
```

认领命令只更新资源所有者，不删除数据。注册在完整多租户隔离门禁通过前保持关闭。

服务器保存的只有：

```text
/opt/interview-guide/
├── .env
├── bundle/
│   ├── compose.yml
│   ├── Caddyfile
│   ├── refresh.sh
│   ├── update.sh
│   ├── rollback.sh
│   ├── status.sh
│   └── stop.sh
└── state/
    ├── current-tag
    ├── previous-tag
    └── bundle-revision
```

## HTTPS、DNS 和端口

新安装默认配置为：

```env
COMPOSE_PROFILES=https
PUBLIC_DOMAIN=interview.example.com
ACME_EMAIL=admin@example.com
TLS_BIND_ADDRESS=0.0.0.0
TLS_HTTP_PORT=80
TLS_HTTPS_PORT=443
FRONTEND_BIND_ADDRESS=127.0.0.1
FRONTEND_PORT=18073
```

复用宿主机 Caddy 时安装器改为：

```env
COMPOSE_PROFILES=
EXTERNAL_CADDY=true
PUBLIC_DOMAIN=interview.example.com
FRONTEND_BIND_ADDRESS=127.0.0.1
FRONTEND_PORT=18073
```

正式公网入口只有 Caddy：

```text
公网 TCP 80   -> Caddy HTTP/ACME 入口
公网 TCP 443  -> Caddy HTTPS 入口
```

Caddy 使用备案域名向 Let's Encrypt 自动签发和续期证书，HTTP 自动跳转到 HTTPS。前端 Nginx
仍在 Compose 网络内负责静态文件以及 `/api`、`/ws`、`/docs` 和 `/openapi.json` 的同源代理。
API、PostgreSQL、Redis 和 MinIO 不发布宿主机端口。

使用 NAT 时，公网端口仍必须是 80/443，但可以转发到服务器上由 `TLS_HTTP_PORT` 和
`TLS_HTTPS_PORT` 指定的端口。例如：

```text
公网 TCP 80  -> 服务器 TCP 8080  （TLS_HTTP_PORT=8080）
公网 TCP 443 -> 服务器 TCP 8443  （TLS_HTTPS_PORT=8443）
访问地址      -> https://interview.example.com
```

不能使用“公网高端口到服务器 80/443”代替上述映射，因为 ACME HTTP-01 和正常浏览器 HTTPS 都从
公网 80/443 到达。不要为 `FRONTEND_PORT`、`8080`、`5432`、`6379`、`9000` 或 `9001` 建立公网
映射。

证书和 ACME 状态保存在 Compose 的 `caddy_data`、`caddy_config` Volume。更新和普通停止不会删除
这些卷，Caddy 会在到期前自动续期并热加载，不需要部署者安装 Certbot 或编写 reload 定时任务。

检查入口：

```bash
curl -I http://interview.example.com
curl -fsS https://interview.example.com/health
```

第一条应跳转到 HTTPS，第二条应返回健康结果。

### 从旧服务器迁移

应用数据不会随镜像自动复制到新服务器。需要保留现有数据时，切换 DNS 前必须迁移：

- PostgreSQL 数据或逻辑备份。
- MinIO 对象数据。
- `provider_key` Volume；如果曾保存 Provider Key，该卷必须与 PostgreSQL 一起迁移。
- 需要保留的 Redis 持久化数据；迁移期间停止旧 API、Worker 和 Scheduler，避免两边同时消费
  Stream。

当前没有业务数据和 Provider Key 时，可以直接在新服务器执行全新安装。存在数据时应先完成备份
恢复演练，再安排只读/停机窗口；不要复制正在写入中的 Docker Volume，也不要通过 `down -v`
清理旧服务器。

修改 TLS 或域名配置后手动执行一次更新：

```bash
sudo /opt/interview-guide/bundle/refresh.sh --root /opt/interview-guide
```

## 主动更新机制

查看定时器：

```bash
systemctl status interview-guide-update.timer
systemctl list-timers interview-guide-update.timer
```

默认每 5 分钟检查一次，附加最多 30 秒随机延迟。立即检查：

```bash
sudo systemctl start interview-guide-update.service
journalctl -u interview-guide-update.service -n 100 --no-pager
```

更新顺序：

1. 拉取 `interview-guide-deploy:main`。
2. 读取部署包的 `org.opencontainers.image.revision`。
3. 拉取同一 commit 的 backend/frontend `sha-<commit>` 镜像。
4. 校验两个镜像的 revision 标签与目标 tag 一致。
5. 保持 PostgreSQL、Redis、MinIO 健康。
6. 重新执行 Bucket 初始化和 Alembic。
7. 更新 API、Worker、Scheduler、前端和 Caddy 并等待容器健康检查。
8. 从应用网络内验证证书有效的 `https://域名/health`。
9. 成功后记录当前版本和上一版本。

部署包也由服务器主动更新，因此 Compose 或更新脚本变化不需要重新登录服务器复制文件。

## 状态、日志和回滚

查看状态：

```bash
sudo /opt/interview-guide/bundle/status.sh --root /opt/interview-guide
```

查看应用日志：

```bash
cd /opt/interview-guide
TAG="$(sudo cat state/current-tag)"
sudo env INTERVIEW_GUIDE_IMAGE_TAG="$TAG" docker compose \
  --project-name interview-guide \
  --project-directory /opt/interview-guide \
  --env-file /opt/interview-guide/.env \
  -f /opt/interview-guide/bundle/compose.yml \
  logs -f gateway frontend app worker scheduler
```

回滚到上一次成功部署的应用版本：

```bash
sudo /opt/interview-guide/bundle/rollback.sh --root /opt/interview-guide
```

回滚只切换应用镜像，不逆向执行数据库迁移。数据库变更必须保持至少一个版本的向后兼容性。

部署指定的 commit：

```bash
sudo /opt/interview-guide/bundle/update.sh \
  --root /opt/interview-guide \
  --tag sha-<完整commit-sha> \
  --force
```

## 停止和禁用自动更新

长期停止应用时先暂停定时器，否则下一次主动检查会重新收敛并启动服务：

```bash
sudo systemctl disable --now interview-guide-update.timer
sudo /opt/interview-guide/bundle/stop.sh --root /opt/interview-guide
```

只暂停自动更新但保持当前服务运行：

```bash
sudo systemctl disable --now interview-guide-update.timer
```

恢复自动更新：

```bash
sudo systemctl enable --now interview-guide-update.timer
```

不要执行 `docker compose down -v`，除非明确要删除 PostgreSQL、Redis、MinIO 和 Provider 主密钥。
