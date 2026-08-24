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

服务器只需要 Docker Engine、Compose v2、systemd 和访问 GHCR/Docker Hub 的网络，不需要 Git、
Node.js、pnpm、Python 或 uv。

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
  --channel main

sudo rm -rf -- "$DEPLOY_TMP"
```

安装器会：

- 创建 `/opt/interview-guide/.env`
- 生成随机 PostgreSQL 和 MinIO 密码
- 安装纯镜像 Compose 清单和主动更新脚本
- 首次拉取并启动已经通过 CI 的不可变镜像
- 安装并启动 `interview-guide-update.timer`

服务器保存的只有：

```text
/opt/interview-guide/
├── .env
├── bundle/
│   ├── compose.yml
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

## HTTP 和 NAT 配置

默认配置为：

```env
FRONTEND_BIND_ADDRESS=0.0.0.0
FRONTEND_PORT=18073
```

生产 Compose 只发布该前端端口。API、PostgreSQL、Redis 和 MinIO 只存在于 Compose 网络。

NAT 示例：

```text
公网 TCP 28080 -> 服务器 TCP 18073
访问地址        -> http://example.com:28080
```

不要为 `8080`、`5432`、`6379`、`9000` 或 `9001` 建立公网映射。

修改配置后手动执行一次更新：

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
7. 更新 API、Worker、Scheduler 和前端并等待健康检查。
8. 成功后记录当前版本和上一版本。

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
  logs -f app worker scheduler frontend
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
