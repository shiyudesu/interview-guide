# InterviewGuide 前端

前端使用 React 18、TypeScript、Vite、Tailwind CSS 和 React Router。生产构建由 Nginx
提供，`/api/` 与 `/ws/` 转发到 Compose 中的 `app:8080`。

## 安装和启动

需要 Node.js 24 和 pnpm 10.26.2：

```bash
corepack enable
pnpm install --frozen-lockfile
pnpm run dev
```

开发服务器默认地址是 <http://localhost:5173>。

Vite 默认把 `/api` 转发到 `http://localhost:8080`。后端地址不同时可覆盖：

```bash
VITE_API_PROXY_TARGET=http://127.0.0.1:8080 pnpm run dev
```

`VITE_API_BASE_URL` 用于直接设置浏览器请求前缀；通常保持为空，让开发代理或生产 Nginx
处理同源请求。

## 页面

- 简历上传、分析历史和详情
- 文字面试、语音面试、统一历史和评估报告
- 面试日历和邀请文本解析
- 知识库上传、管理、向量状态和 RAG 对话
- 知识库题目生成、维护和专项面试
- Provider、默认模型、ASR 和 TTS 设置

## 命令

```bash
pnpm run dev
pnpm run build
pnpm run preview
pnpm run test:e2e
pnpm run test:interview-history
pnpm run test:question-generation
pnpm run test:interview-capacity
pnpm run test:interview-entry
```

`pnpm run build` 会先运行 TypeScript 检查，再执行 Vite 构建。

## Playwright

首次运行时安装 Chromium：

```bash
pnpm exec playwright install --with-deps chromium
pnpm run test:e2e
```

Playwright 默认启动 `127.0.0.1:4173` 的 Vite 服务。CI 中的 `@real-backend` 用例会把
`REAL_BACKEND_URL` 指向生产 Compose API。

这台开发机需要人工浏览器验收时，使用 Windows Chrome：

```text
/mnt/c/Program Files/Google/Chrome/Application/chrome.exe
```

## 目录

```text
src/api/          API 客户端
src/components/   通用及业务组件
src/pages/        路由页面
src/hooks/        页面状态和业务 Hook
src/types/        共享类型
e2e/              Playwright 用例
nginx.conf        生产静态文件与反向代理配置
```

前端通过相对 `/api` 路径调用后端。新增接口时应同步更新 API 类型，并为状态转换或边界逻辑
增加测试。
