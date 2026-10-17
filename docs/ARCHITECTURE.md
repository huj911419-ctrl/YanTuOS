# 系统架构

## 部署与模块

React/TypeScript/Vite 构建成静态资源，由同一个 FastAPI 进程提供页面和 `/api`。开发时 Vite 代理 API；运行时不需要 Node 常驻。SQLite 使用 WAL、外键和事务；附件是数据目录下的普通文件。没有微服务、Redis、独立队列或向量数据库。

- `backend/app/main.py`：装配、访问防护与已有核心 API。
- `backend/app/routes/`：扩展学习业务、AI、资料和数据管理。
- `backend/app/services/`：计时、复习/学习校验、统计、规则建议、模型协议、认证和备份。
- `frontend/src/components/`：表单、对话框、数据请求、附件和 PWA。
- `frontend/src/pages/`：计划目标、复习/统计、资料、AI 和设置。

前端 API、组件和模块页面分离；写操作发布数据失效事件，相关页面重新读取真实数据。列表目前仍以个人规模的全量读取为主；独立页面维护自己的加载/错误状态，核心批量读取使用逐项结果处理。没有宣称已完成大规模数据分页优化。

## 数据与接口

|子系统|主要数据|
|---|---|
|任务|subjects、goals、tasks；任务关联目标，优先级/状态与编辑 revision|
|计时|study_sessions 与 study_segments；正向/番茄/补录，共享真实统计|
|知识|knowledge_points；subject/domain 表示科目/章节，parent_id 支持子知识点，保存掌握和来源元数据|
|错题|mistakes、mistake_knowledge、mistake_files；多知识点与多图片|
|复习|review_schedules/events、knowledge_reviews/review_events；结果、前后阶段、到期日与历史|
|资料|files、materials；本地文件标识、内容校验和、分类、笔记与提取状态|
|建议/设置|activity_events、app_settings；真实变化事件、透明规则与非敏感配置|
|AI|ai_runs；会话、提示、回复、服务/模型和当次授权上下文，不存密钥|

保留原 `/api/tasks`、`/knowledge`、`/sessions`、`/mistakes`、`/reviews`、`/stats` 等接口；新增 `/subjects`、`/goals`、`/records`、`/knowledge-reviews`、`/review-schedule`、`/analytics`、`/recommendations`、`/settings`、`/files`、`/materials`、`/ai`、`/auth` 和 `/data/restore`。实际输入模型与 OpenAPI 可在运行中的 `/api/docs` 查看（启用认证时需先登录）。

## 时间、事务与迁移

UTC 保存精确时间，北京时间切分统计日，每周一开始。一个会话由多个实际计时片段组成；唯一索引限制一个活动会话、每次会话一个未结束片段。番茄钟在 API 请求到来时以目标时长惰性结算，落库截止时间准确，不依赖页面后台执行。没有常驻调度进程；到期提醒主要在应用内显示。

连接启用外键与 busy timeout；写事务 BEGIN IMMEDIATE。进程内数据库互斥保护恢复与并发请求，API 中的计时结算放在线程池执行。模型请求期间不占数据库事务。任务/知识/错题编辑检查 revision，普通重复开始可通过 request_id 幂等处理。

当前 schema_version=3：001 原 MVP，002 平台扩展，003 按科目/章节/父节点约束知识点重名。迁移前在线备份；迁移与版本号提交保持原子性。表重建期间临时关闭连接外键，提交前执行 foreign_key_check，随后恢复外键。现有 ID 与关联不变。

## AI、资料与安全

ModelProvider 是独立协议。首个 CompatibleProvider 使用 Chat Completions 文本消息；地址/模型来自非敏感设置或环境变量，Key 仅来自环境变量。发送前预览全部消息，摘要绑定目标、模型和实际上下文；变动后旧确认失效。无自动请求、自动重试或后台数据上传。

PDF 提取在限制地址空间、CPU 和超时的子进程中进行，最多提取 50 页；无 OCR。图片经过真实文件解码校验，拒绝 SVG/HEIC；Markdown/TXT 只显示文本。附件访问需要与 API 相同的授权，不映射成公开静态目录。

本机默认无登录；应用本身拒绝无认证的非本机 API 访问。脚本对局域网要求明确私有 IP、令牌、HTTPS 和 Host/Origin 配置。浏览器使用 HttpOnly、SameSite=Strict 的 24 小时会话；HTTPS 下添加 Secure，重启后会话失效。写操作有 Origin/跨站检查，数据库使用参数化 SQL；API 不缓存。服务仍是个人应用，不面向公开互联网多租户。

## 备份与中断恢复

完整 ZIP 通过 SQLite backup 获得一致快照，写锁保护元数据与附件的一致读取；每个文件有校验和。恢复检查路径、大小、版本、表结构、数据库及附件完整性，先放入隔离目录，再显式确认。JSON 仅支持当前版本、完整表集合、字段验证与事务写入，不含附件内容。

激活前保存完整回滚快照并落盘中断标记。切换失败立即回滚；进程意外中断时，下一次启动检测标记并恢复原快照。恢复未完成期间 API 暂停读写。旧附件目录和回滚包保留，由用户确认后维护；不自动清除学习数据。

PWA 只缓存静态资源和离线说明，不缓存个人 API；不提供服务不可达时的离线编辑或冲突合并。真实 iPhone 安装与后台行为需要真机验收。
