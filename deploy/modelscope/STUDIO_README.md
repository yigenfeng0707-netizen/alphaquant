# AlphaQuant

因子增强选股 + 风险平价配置的演示产品。面向 **2026 上海（长三角）中青年工程师创新创业大赛 · 金融科技（黄浦承办）**。

本创空间是 **AlphaQuant** 的公网 Demo，不是 AFAC 的 QuantInsight。QuantInsight / `quantinsight-pro` 属于另一场比赛，请勿当作本场体验链接。

## 使用

打开后左下角数据源选 **离线演示（可断网）**，主按钮 **一键演示案例 1**。无需登录。样本内模拟，不是实盘、不是收益承诺。

| 路径 | 说明 |
|------|------|
| `/` | 前端首页（FastAPI 同源托管） |
| `/health` | 存活检查 |
| `/api/case1?source=offline` | 案例 1 离线闭环 |
| `/docs` | OpenAPI |

监听 `0.0.0.0:$PORT`（默认 7860）。
