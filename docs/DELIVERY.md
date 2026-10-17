# YanTu OS 0.2.0 交付说明

交付日期：2026-10-17。项目在原路径 `/home/hjj/Development/YanTuOS` 原地升级，保留已有实现与数据。当前前后端已在 `http://127.0.0.1:8000` 同进程运行。

## 实际完成

每日/每周计划、优先级与阶段目标；正向/番茄计时、暂停恢复、补录更正；多科目层级知识与笔记；文字/图片错题、知识关联、搜索导出；可配置间隔复习与掌握记录；真实日周月/范围统计、学习日历、错题趋势、规则建议；资料管理与受限 PDF 文本提取；模型适配、配置、授权对话与分析历史；响应式页面、PWA 离线说明；数据备份/导入/恢复、迁移、访问控制、错误日志与运维脚本。

具体完成边界见 [FEATURE_STATUS.md](FEATURE_STATUS.md)。无 AI Key 时基础功能可用，当前 AI 页面明确未配置。

## 启动和停止

```bash
cd /home/hjj/Development/YanTuOS
./scripts/start.sh
./scripts/status.sh
./scripts/stop.sh
```

正常使用只需 start，一个地址同时提供前端和后端。开发时分开运行 `./scripts/backend-dev.sh`（后端8000）与 `./scripts/frontend-dev.sh`（前端5173）。安装与构建使用 `./scripts/install.sh`，无需系统级安装脚本或 AI。

## 手机、备份和 AI

- **手机**：按 [README 局域网流程](../README.md#手机访问安全局域网) 配置明确私有 IP、访问令牌和 HTTPS。证书信任由用户亲自决定；软件未开放公网。真机尚未验收。
- **备份**：设置页下载完整 ZIP，或 `./scripts/backup.sh`。本次已生成 `backups/yantu-20261017-145558.zip`。恢复命令 `./scripts/restore.sh /备份路径.zip --output /尚不存在的恢复目录`；默认拒绝覆盖。页面覆盖恢复须预览并输入确认文字，自动保存回滚包。
- **AI**：设置页配置兼容服务地址和模型，`.env` 配置 `YANTU_AI_API_KEY`，保护文件权限后重启。实际发送前显示目标和全部消息并要求授权；没有自动上传或试连，没有产生模型费用。

## 真实测试与正式数据

`./scripts/install.sh` 与 `./scripts/test.sh` 均退出 0。后端 47 passed；类型检查/生产构建通过；真实进程及 HTTPS/备份恢复验收通过；Playwright 19 passed、1 skipped。跳过的是移动 WebKit PWA 专项，Chromium 已通过同项。详见 [TEST_REPORT.md](TEST_REPORT.md) 的十项验收。

正式库 schema 3、integrity_check=ok、外键无异常，文件0600。2026-10-17 14:55 的启动核对快照中，任务/学习记录/错题/复习事件/资料均为0；之后实际新增的数据原样保留。21个参考知识点不是官方考纲。隔离测试内容没有写入个人库。升级前快照位于 `data/backups/`。

## 未完成与已知限制

- 真实模型和 iPhone 真机仍需要用户密钥/设备以及对应授权，没有假装验收通过。
- 数学核对是受限数值运算；没有通用符号证明核验。扫描件没有 OCR，图片支持 PNG/JPEG/WebP，暂不支持 HEIC。
- Ubuntu 服务不可达时只显示离线说明，不能离线修改业务；没有后台推送或跨设备离线合并。
- 文件20MB、PDF前50页/约50万字符、恢复展开512MB；个人规模全量列表尚未做多年大数据压测。
- 仍有上游 TestClient 弃用警告，不影响当前通过结果。项目不是公网多用户服务。

## 后续维护

修改前备份，修改后 `./scripts/test.sh`，再构建重启。先看 `./scripts/doctor.sh` 与 `.runtime/logs/server.log`，不要通过删除数据库解决故障。读取 [FAQ.md](FAQ.md)、[ARCHITECTURE.md](ARCHITECTURE.md)、[DECISIONS.md](DECISIONS.md) 和 [NEXT_STEPS.md](NEXT_STEPS.md) 可以独立接续维护。

本地 Git 已初始化；没有配置或冒用提交者身份，没有远程推送。MIT 许可、锁文件、贡献说明和个人数据忽略规则已经保留。
