# 贡献与独立维护

1. 安装：`./scripts/install.sh`。依赖放在 `.venv` 和 frontend/node_modules，不修改系统包。
2. 开发：分别运行 backend-dev.sh 和 frontend-dev.sh。基础功能必须不依赖模型服务。
3. 变更数据库：新增编号 SQL 迁移，不修改已经发布的迁移；增加旧版本升级和失败回滚测试。保留用户 ID 与关联。
4. 测试：`./scripts/test.sh`。模型测试仅使用受控 MockTransport；不要在 CI 使用真实密钥或学习资料。
5. 格式：`.venv/bin/ruff format backend scripts`；前端运行 `pnpm exec prettier --write src e2e`。
6. 更新 docs/PROGRESS.md、NEXT_STEPS.md、DECISIONS.md、TEST_REPORT.md、FEATURE_STATUS.md，区分已测试与未测试。
7. 提交前检查 `git diff --cached`；禁止提交 .env、data、backups、.runtime、日志或浏览器个人资料。
8. 许可证 MIT。保持单用户单进程架构，优先 SQLite 与小型依赖。推送和公开发布由项目所有者决定。

本仓库没有预置 Git 作者身份或远程仓库。首次提交请由维护者配置自己的 user.name 与 user.email，不要使用他人的身份。
