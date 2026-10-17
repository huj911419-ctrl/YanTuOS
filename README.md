# 研途 OS · YanTu OS

面向个人长期使用的中文考研学习平台。React + TypeScript + Vite、FastAPI、SQLite，单进程部署。学习任务、计时、错题、复习和统计均可在**没有 AI API**的情况下使用。

项目目录：`/home/hjj/Development/YanTuOS`。当前为 0.2 系列，沿用并升级原 MVP；没有预设考试数学类别，没有演示学习记录。21 个初始数学知识点仅是可编辑的参考目录，**不是官方考试大纲**。

## 今天开始使用

已安装并构建的项目：

```bash
cd /home/hjj/Development/YanTuOS
./scripts/start.sh
```

打开 **http://127.0.0.1:8000**。这个地址同时提供前端与后端，不需要启动两个进程。

```bash
./scripts/status.sh   # 查看运行状态
./scripts/stop.sh     # 只停止本项目登记的进程，保留学习数据
./scripts/doctor.sh   # 环境、健康状态、数据库/附件完整性与日志位置
```

首次安装或换电脑：需要 Python 3.14（本机验证版本）、Node.js 22.12+、pnpm 11.25。执行 `./scripts/install.sh` 安装项目虚拟环境和锁定依赖并构建。工具链优先使用系统安装，也支持本机已存在的 Codex 缓存 Node；**运行构建好的应用只需要项目 Python 虚拟环境，不需要 Codex 或 AI**。脚本不使用 sudo、不安装系统服务。

## 主要功能

- **计划与目标**：日计划、任意连续七日计划、历史/未完成筛选、科目、优先级、任务状态、阶段目标与关联任务进度。
- **计时与记录**：正向计时、番茄钟、暂停/继续/结束、刷新和重启恢复、手动补录与更正。暂停和休息不计入时长，补录拒绝未来与重叠时段。
- **知识体系**：科目 → 章节 → 知识点 → 子知识点；状态、0–5 掌握程度、最近学习/复习时间、笔记、错题关联、范围标签和资料来源/年份。
- **错题与复习**：题目文本/图片、正确与错误答案、错因、分类、知识绑定、搜索、掌握状态、Markdown 导出；错题与知识点复习、历史、逾期提示、手动改期。
- **分析**：真实日/周/月/自定义范围统计、科目投入、学习日历、任务/复习完成情况、错题新增与掌握分布；无需模型的每日/每周建议和阶段回顾。
- **AI**：兼容模型适配器、对话、概念/题目讲解、错因/同类题/计划建议、历史记录；先预览并授权数据，才能发送。无配置时明确不可用。附带受限的本地算式核对。
- **资料**：Markdown/TXT/PDF、本地笔记、分类、搜索、知识关联、原文件和笔记导出。文本层 PDF 最多提取前 50 页；扫描件不做 OCR。
- **数据与手机**：完整 ZIP 备份、JSON 导出/导入、隔离恢复预览与显式覆盖确认、完整性检查、访问认证、响应式布局、PWA 静态资源与基础离线页面。

完整交付见 [交付说明](docs/DELIVERY.md)。实际验收证据与限制见 [测试报告](docs/TEST_REPORT.md)、[功能状态](docs/FEATURE_STATUS.md) 和 [使用说明](docs/USER_GUIDE.md)。真实模型效果与 iPhone 真机验收必须单独确认，模拟测试不能代替它们。

## 手机访问：安全局域网

默认仅本机访问。手机和 Ubuntu 必须处于可互访的网络，Ubuntu 需保持开机、服务运行。**不会自动开放公网、修改路由器或防火墙**。

1. 在 Ubuntu 网络设置中查看局域网 IP，例如 `192.168.1.20`，确认该地址属于自己的电脑。
2. 生成仅保存在项目内的证书：

```bash
.venv/bin/python scripts/make_lan_cert.py 192.168.1.20
```

3. 将 `.env.example` 复制为 `.env`，设置以下内容（替换示例 IP 和令牌）：

```dotenv
YANTU_HOST=192.168.1.20
YANTU_PORT=8000
YANTU_ACCESS_TOKEN="自己生成的至少16字符随机令牌"
YANTU_ALLOWED_HOSTS=192.168.1.20,localhost,127.0.0.1
YANTU_ALLOWED_ORIGINS=https://192.168.1.20:8000
YANTU_TLS_CERT=/home/hjj/Development/YanTuOS/.runtime/tls/server.crt
YANTU_TLS_KEY=/home/hjj/Development/YanTuOS/.runtime/tls/server.key
YANTU_TLS_CA=/home/hjj/Development/YanTuOS/.runtime/tls/ca.crt
```

可用 `.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))'` 在自己的终端生成令牌，不要提交到仓库。

4. 只将 `ca.crt` 通过自己控制的方式传给 iPhone。安装描述文件并在「设置 → 通用 → 关于本机 → 证书信任设置」手动启用该根证书的完全信任。**这是设备安全设置变更，必须由你决定并亲自操作；脚本不会代为安装。绝不分享 `.key` 私钥。**
5. 执行 `./scripts/stop.sh` 和 `./scripts/start.sh`，Safari 打开 `https://192.168.1.20:8000`，输入访问令牌。登录会话最长 24 小时，服务重启后重新登录。
6. Safari 分享菜单 →「添加到主屏幕」。只有受信任 HTTPS 才能完整使用 Service Worker；普通局域网 HTTP 不作为 PWA 支持条件。

IP 改变后需生成匹配新 IP 的证书（使用新的 `--output` 目录，不覆盖原证书）并更新配置。证书生成及本机 HTTPS 已自动化验证；你的手机信任设置和实际网络尚需真机操作。参见 [MDN Service Worker 安全条件](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API/Using_Service_Workers) 和 [Apple 主屏幕 Web App 说明](https://support.apple.com/guide/iphone/iphea86e5236/ios)。

## AI 配置

AI 不参与基础数据的保存和计算。配置兼容 Chat Completions 的模型服务：

1. 在「数据与设置」填写 Base URL（通常以 `/v1` 结尾）、模型名称和超时。
2. 在本机 `.env` 中设置 `YANTU_AI_API_KEY="你的密钥"`，执行 `chmod 600 .env`，重启服务。环境变量 `YANTU_AI_BASE_URL`、`YANTU_AI_MODEL` 如有设置，会覆盖页面配置。对无认证的本机兼容模型，可将密钥设为 `local`；不会因此自动安装或启动模型。
3. 在 AI 页面选择任务、输入问题；默认不附带学习记录。选择需要授权的知识点、错题文本或统计摘要，预览**实际目标服务与全部消息**后确认发送。
4. 模型输出只形成建议，不自动改写任务或知识点。图片/PDF 不会自动上传。继续会话会附带该对话最近 6 轮文本，也会出现在预览里。

真实请求可能产生服务商费用，仅由你的明确发送操作触发。程序不自动测试模型连通性、不自动重试生成请求，不显示或导出密钥。协议依据 [Chat Completions 官方参考](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)；第一适配器使用文本消息和 `max_tokens=2048`，具体服务需支持该兼容协议，不承诺所有供应商的私有协议即插即用。

## 备份、导入与恢复

推荐定期使用「数据与设置 → 下载完整备份」，或：

```bash
./scripts/backup.sh
./scripts/backup.sh --output /自己选择的目录/yantu-backup.zip
./scripts/restore.sh /备份路径/yantu-backup.zip --output /一个尚不存在的恢复目录
```

- **ZIP**：数据库、全部登记附件、版本与 SHA-256 清单；不包含 `.env`、密钥或登录会话。
- **JSON**：当前数据库的结构化数据，不含附件二进制。当前版本的无附件 JSON 可直接恢复；有附件的数据必须使用完整 ZIP。
- **SQLite 快照**：不含附件。旧版 MVP 的 SQLite 可恢复并自动迁移；含附件的新数据请使用 ZIP。
- 命令行默认只恢复到新目录，绝不覆盖原目录。检查通过后停止服务，将 `.env` 的 `YANTU_DATABASE_PATH` 指向恢复目录里的 `yantu.sqlite3` 再启动；附件目录与数据库同级。
- 页面恢复先校验到隔离目录、展示数量，输入「覆盖当前学习数据」才会替换当前数据。恢复前完整快照保存在数据库同级 `backups/`，旧附件目录也保留；恢复后重新打开学习页面。切换失败会回滚，若进程中断，下一次启动会根据中断标记恢复原快照；恢复未完成时 API 暂停读写。建议先结束正在进行的计时。
- 备份中仍包含私人学习内容，导出后请保存在自己的安全位置。默认一次恢复的展开大小上限为 512 MB，不支持加密 ZIP；超限需先检查资料规模再调整代码配置并测试。

## 开发、测试与维护

日常使用不需要开启开发服务器。需要修改代码时：

```bash
./scripts/backend-dev.sh   # 后端前台运行，Ctrl+C 停止
./scripts/frontend-dev.sh  # 另一终端：Vite http://127.0.0.1:5173
./scripts/test.sh          # pytest + 前端构建 + 真实进程验收 + Playwright
```

第一次使用浏览器测试，如果浏览器尚未安装：

```bash
source scripts/toolchain.sh
cd frontend
pnpm exec playwright install chromium webkit
```

Ubuntu 26.04 若缺少 WebKit 依赖，可执行 `./scripts/prepare-browser-libs.sh` 将所需库下载并解包到项目 `.runtime/`，不会系统安装。浏览器测试用独立临时数据库；真实进程测试同样使用临时数据与随机本机端口，不写入个人学习记录。

修改后运行 `./scripts/build.sh` 并重启服务。PWA 有新版本时点击更新按钮，首次安装不会自动刷新你的表单。日志位于 `.runtime/logs/server.log`，自动轮转，不记录请求正文、访问令牌或 API Key。故障处理见 [FAQ](docs/FAQ.md)。

## 项目结构与开源

- `backend/app/`：应用入口、路由、服务、输入校验、SQLite 顺序迁移。
- `frontend/src/`：应用布局、共享组件与模块页面。
- `scripts/`：安装、构建、进程管理、测试、证书与备份恢复。
- `data/`：个人数据库、附件与自动快照，已被 Git 忽略。
- `docs/`：架构、决策、路线图、进度、功能状态、验收和维护资料。

许可证：MIT。默认不包含个人数据、不连接远程 Git 仓库、不自动推送。贡献步骤见 [CONTRIBUTING.md](CONTRIBUTING.md)。
