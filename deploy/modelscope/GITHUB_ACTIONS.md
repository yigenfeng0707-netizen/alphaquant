# GitHub Actions → 魔搭 Docker 创空间（AlphaQuant）

将 **AlphaQuant**（FastAPI 同源托管 Vue 前端）在 push `main` 且相关路径变更时，同步到独立魔搭创空间并触发 Docker 构建。

本场体验链接只指向 AlphaQuant 创空间。**QuantInsight / `gsym236998/quantinsight-pro` 是另一场比赛（AFAC），禁止当作本赛 Demo。**

Workflow：

- [`.github/workflows/deploy-modelscope.yml`](../../.github/workflows/deploy-modelscope.yml)
- [`.github/workflows/modelscope-keepalive.yml`](../../.github/workflows/modelscope-keepalive.yml)

## GitHub Secrets

仓库 → **Settings → Secrets and variables → Actions**：

| Secret | 说明 |
|--------|------|
| `MODELSCOPE_API_TOKEN` | 魔搭 Access Token（OpenAPI + Git oauth2） |
| `MS_STUDIO_OWNER` | 魔搭用户名（`GET /openapi/v1/users/me`），**不是** GitHub 用户名 |
| `MS_STUDIO_NAME` | 创空间名，如 `alphaquant`（不要用 `quantinsight-pro`） |

Token 只进 Secrets，never commit。

## 创空间形态

- SDK：**Docker**，硬件：**CPU**（`platform/2v-cpu-16g-mem`），可见性：**公开**
- 容器：`uvicorn app.main:app --host 0.0.0.0 --port $PORT`（默认 7860）
- `/health`、`/` 首页、`/api/case1?source=offline` 离线可跑案例 1

## 触发

- 自动：push `main`，且变更位于 `backend/**`、`frontend/**`、`data/offline/**`、`deploy/modelscope/**` 或本 workflow
- 手动：Actions → **Deploy AlphaQuant to ModelScope Studio** → Run workflow

首次 Docker 构建可能超过轮询窗口：按日志 **Re-run**，不要 force push `main`。

## 保活

- GitHub：`modelscope-keepalive.yml`，`cron: '*/20 * * * *'`，带浏览器 UA 访问公网 URL；HTTP 403 记日志不 fail
- 本机：`powershell -File scripts/keepalive.ps1`

线上以 `https://{owner}-{name}.ms.show` 为准。GitHub push 本身不会更新 Demo，必须本 workflow 成功。
