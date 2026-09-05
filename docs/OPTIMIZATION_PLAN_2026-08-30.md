# Dochris 持续优化路线图（2026-08-30，更新于 2026-09-02）

## 目标与停止条件

目标不是继续堆功能，而是把 dochris 变成一个新用户能独立安装、完成第一条带来源回答、诊断失败、安全执行写操作、升级和回滚的本地优先知识库产品。

优秀开源项目级的最低停止条件：

1. clean environment 可以用一个明确流程启动完整产品。
2. Dashboard → Files → Compile → Query → Candidate → Promote → Quality 主路径有自动化 E2E。
3. 读操作无隐式写入；所有 mutation 有预览、确认、审计和可恢复失败。
4. 相同内容重复 ingest/compile/promote 不会膨胀来源、概念、向量或关系。
5. 本地检索、外部 provider 和写入阶段分别可观测、可取消、可设置预算。
6. release artifact、升级、回滚、支持矩阵和安全边界均有可验证文档。

## 已建立的不可退化基线

- 后端全量：3206 passed、46 skipped、6 warnings，coverage 75.52%；宿主 HTTP/HTTPS/SOCKS 代理变量存在时仍可复现通过。
- 后端 fast gate：354 passed / 2884 deselected。
- Python：全仓 `ruff check .`、`ruff format --check .` 与 mypy 141 source files 全绿；benchmark/examples 已纳入统一门禁。
- 前端：56 tests、ESLint、Vite production build 全绿。
- 浏览器：零新增依赖的 Chrome DevTools E2E 已进入 CI；除原有安全、成功、错误恢复、键盘、规模和响应式矩阵外，现已验证 Compile 活动 job 的跨页/reload 恢复、真实 cancel、服务重启中断历史、失败详情与 retry lineage。fixture API、上传文件和 Chrome profile 均为临时隔离边界，不触碰真实知识库、凭据或 provider。
- API：`/health`、`/ready`、`/api/v1/status` 通过；默认最低质量分 85。
- Graph：28 canonical concepts、5 sources、5 summaries、61 edges，无 `_N` 展示节点。
- 九个主页面具备统一错误分类和重试；Query 具备取消、超时、阶段耗时和稳定 SSE 终止合同。
- 测试隔离不再读取真实 home 配置或写真实用户目录；async 测试实际执行。
- Makefile 的 pytest/ruff/mypy/pip/build 均绑定项目 Python/venv，避免系统工具链漂移。
- React production image 合同与本机实证已建立：Node 22 构建、Nginx SPA fallback、同源 `/api` 代理、Compose 四服务 healthy；默认端口仅绑定回环地址。
- Python sdist/wheel 已构建；基础安装已从历史 146 包、40m10s、约 1.2 GiB 的混合开发安装拆为 21 包、约 29 MiB，Python 3.14.6 warm-cache 安装 0.221s。基础 wheel 不再包含 MarkItDown、ChromaDB、sentence-transformers、Torch、ONNXRuntime 或 Kubernetes，且 `kb init`、doctor、version 与空库查询通过。显式 `WORKSPACE`/`kb init PATH` 已成为配置隔离边界，不再读取或写入 home。
- 前端隔离快照已完成 `npm ci`、40 tests、lint 与 production build；`.nvmrc`、package engine 和文档已统一 Node 22.13+ / `<23` 工具链。
- Git 分发合同会拒绝大小写不敏感文件系统的路径碰撞；重复的大写 PR 模板索引项已移除，保留小写中文模板。
- Docker core/API 已真实构建运行：core 65.46 MB（不含 Torch），API 523.60 MB（CPU-only Torch）；BuildKit 下载缓存、apt/pip retry、Python readiness probe 与默认关闭 embedding preload 已锁定。
- LEANN extra 已改为官方 `leann>=0.3.7` 并适配 0.3.x builder/search API；旧注册表兼容、metadata、删除重建和 collection 发现有测试，clean resolver 成功解析。
- 文档站 `mkdocs build --strict` 0 warning；产品导航与内部资料边界明确，CI 将任何文档 warning 视为失败。
- 隔离关键写路径 E2E 已覆盖 upload → compile → query → explicit contribution → candidate promote → quality reset；子进程使用临时 `HOME`/`WORKSPACE`，只替换外部 LLM/向量边界，不触碰真实知识库或凭据。该测试已发现并锁定 API 概念字段归一化缺陷。
- 真实后端的本地确定性边界已纳入回归：OpenAI 官方 SDK 对回环兼容 fixture 验证鉴权、请求序列化、非流式和 SSE 流式响应；真实 Chroma PersistentClient 在独立子进程和临时目录验证写入、查询、metadata 更新、SQLite 重启持久化与删除。它不调用外部厂商、真实 embedding 模型或用户数据。
- 当前构建已用 Computer Use 复查九个主页面；客户端路由切换后聚焦新页 `h1`，九页已通过真实 Tab/Shift+Tab/Enter 的连续纯键盘旅程并抵达 Query 输入框；Query 使用稳定名称/live availability status 和键盘 listbox，历史/收藏也已改为具名原生按钮并由 Enter 真实触发查询；Compile 对未达到服务端动态质量阈值的条目禁用晋升并解释原因。HTTP `/promote` 同时执行完整质量门禁。Files/Quality 无目标时禁用 reset；5 类高影响操作已有真实后果说明与确认。Files dialog、Graph 节点、移动导航和 Query 交互均由隔离 Chrome 的真实键盘事件验证，九页可见按钮名称审计为零违规；2026-09-01 解锁后的 Computer Use AX 热复验再次确认 Files、Query、Compile 的标题、稳定查询名称/状态、动态质量阈值与禁用原因。AX 焦点摘要与 DOM `activeElement` 对路由标题存在工具层差异，自动门禁以 DOM 断言为准。
- Compile job 已具备当前工作区内的原子持久化历史、服务重启中断恢复、失败摘要、参数/时间戳、retry lineage 和浏览器重试入口；正常历史默认限制为最新 200 个终态任务，活动任务不会被裁剪；损坏 JSON 会隔离后重建；常见 secret/token/key 和私有绝对路径会在写盘、API 与日志前脱敏。Computer Use 已真实停止/重启 API 并确认历史恢复，也已确认失败卡片和历史卡片不暴露测试密钥、环境变量名或原始私有路径。发布前仍需多进程协调、隔离副本清理、结构化诊断、无法识别秘密的安全边界和阶段预算。

任何后续迭代都必须至少运行与改动相关的定向测试，再运行 fast gate、前端 gate；影响发布合同的改动还要运行全量覆盖率和真实 E2E。

## 迭代 1：可复现发行物（最高优先级）

### 用户结果

新用户从 clean checkout 或 Docker artifact 在 20 分钟内进入可用 UI，并能看到明确的 readiness 与错误诊断。

### 工作项

1. **已完成**：Makefile 的 pytest、ruff、mypy、pip 和 build 全部解析到项目 Python/venv。
2. **已完成合同**：Node 构建 React artifact，Nginx 暴露 UI、SPA fallback 与同源 API proxy，Compose `api` profile 启动 Web。
3. **已完成本机 arm64**：Docker image build、Compose up、`/ready`、`/healthz`、SPA fallback 与 API proxy smoke；x86_64/Linux/WSL 尚待 CI 或发布矩阵验证。
4. **当前工作树隔离快照已完成**：Python 3.14 全依赖安装、CLI help、包/API import、显式临时 workspace `/ready`/`/status`、前端 `npm ci`/test/lint/build 均通过；最终提交拆分后仍需从 Git artifact 做一次完全独立 clone smoke。
5. **轻量合同与本机 Docker 分层已完成，跨平台发行验证未完成**：基础、`documents`、`vector`、`api`、`pdf`、`ollama`、`leann`、`standard`、`all` 与 `dev` 已分层；基础 wheel 实测 21 包、约 29 MiB，core/API 镜像分别为 65.46/523.60 MB。BuildKit cache 和网络重试已完成，仍需约束/锁文件，以及 `standard`/`all` 的干净冷缓存与跨平台基准。
6. **部分完成**：Node 22.13+ / `<23` 已由 `.nvmrc`、package engine、CI/Docker 和文档统一；仍需固定 Python、OS、向量库和 provider 支持矩阵，并补 release artifact、升级和回滚说明。
7. **已完成配置隔离合同**：`kb init PATH` 尊重显式路径、初始化日志不显示 key 前缀、显式 `WORKSPACE` 不回退读取 home `.env`。
8. **已完成路径可移植性合同**：Git 跟踪路径不得在大小写不敏感文件系统碰撞。

### 退出门禁

- clean install、Docker build/run、首页和 `/ready` 均有日志证据。
- production artifact 不依赖源码目录或开发服务器。
- CI 与本地 Makefile 使用同一解释器和开发工具链。
- Docker/clean install 失败时有可操作诊断，不把“配置可解析”冒充“镜像可运行”。

## 迭代 2：查询核心与安全语义

### 用户结果

普通查询、流式查询、CLI 和 UI 对 retrieval、rerank、citation、timeout、cancel、contribution 的行为一致；读请求不会隐式写数据。

### 工作项

1. **部分完成**：普通/流式查询已共享 retrieval 与 rerank；answer/citation 的流式与非流式合同仍需继续收敛。
2. **已完成**：GET 始终只读；contribution 改为独立认证 POST mutation，UI 只在回答成功后显式写入。
3. **部分完成**：成功、超时、provider 错误、协议错误和取消路径保证恰好一个终止结果；SSE schema 显式版本仍待补。
4. 增加 provider 首 token、生成和总预算；验证客户端断连能取消服务端上游调用。
5. 对外部 provider 明示隐私边界：哪些知识片段会发送、如何选择本地 provider、如何禁用外发。
6. **部分完成**：rerank 与 contribution 的 API/UI 合同已覆盖；CLI 与 citation 版本合同待补。

### 退出门禁

- query 与 query-stream 的共享阶段只维护一套业务实现。
- GET 全部纯读取；mutation 可审计、可重试且不会重复写入。
- 本地 retrieval p95 ≤ 2 秒；provider 延迟独立显示，超时和取消可自动证明。
- 每个回答可追踪到 source、chunk、编译版本和 request ID。

## 迭代 3：存储幂等与单一事实来源

### 用户结果

同一知识重复导入不会制造 `_1` 文件或数量膨胀；Dashboard、Status、Graph、Quality 展示的口径可解释且可追溯。

### 工作项

1. 定义 concept/source/summary 的 canonical ID、alias、版本和来源路径合同。
2. **已完成工具合同**：`kb storage audit/migrate/rollback` 默认 dry-run，只迁移同目录精确编号副本，生成备份 manifest，回滚拒绝覆盖新内容；真实工作区尚未执行 `--apply`。
3. **部分完成**：promote 对相同内容已幂等且覆盖 API/CLI/批量链路；ingest、compile、vector、edge 的重复执行不变量仍待补。
4. 统一统计服务，所有页面返回数值、口径、生成时间和数据版本。
5. 让 Quality 的 provenance、lint、citation、compile result 指向同一编译版本；证据缺失显示“不可评估”。
6. **部分完成**：ChromaDB 初始化/只读失败会安全降级并清空坏缓存；readiness/doctor 的 schema 与迁移诊断仍待补。

### 退出门禁

- 历史数据迁移可 dry-run、可回滚，迁移后无无主 alias 或悬空 edge。
- Graph canonical node 数与存储 canonical entity 数一致；文件数作为独立指标明确展示。
- 幂等测试覆盖重复 ingest、compile、promote 和失败后重试。

## 迭代 4：写路径、可访问性与真实 E2E

### 用户结果

用户能安全完成完整知识生命周期；核心流程可用键盘、移动端和错误恢复完成。

### 工作项

0. **已完成后端确定性基线**：临时 test workspace 的 API 写路径 E2E 可重复通过，真实验证 summary/concept 输出、候选质量门禁、晋升结果和低质量 manifest 重置；真实 OpenAI SDK 回环传输和真实 Chroma PersistentClient 由独立测试证明。外部厂商行为与实际 embedding 模型仍不在本项证明范围内。浏览器确认/取消由下述隔离 Chrome 门禁单独证明。
1. **已完成本地单进程持久化与基础安全合同**：compile 返回 job ID，展示 processed/success/failed/current files；重复提交复用活动 job，页面跨页/reload 可恢复，取消会停止真实后端任务，应用 shutdown 会等待任务清理。历史原子写入当前工作区；服务重启将未完成 job 恢复为 `interrupted`，展示失败摘要和参数，并可按原参数创建有关联的 retry。默认只保留最新 200 个终态任务且保护活动任务；损坏仓库隔离重建；常见凭据和本机路径在持久化/API/日志前脱敏。剩余工作是多进程协调、隔离副本清理、任意无标签秘密边界、结构化失败详情下载和阶段预算。
2. **部分完成**：Files/Quality 无目标时禁用 reset；Files/Quality reset、Compile/候选晋升、候选永久丢弃、enrich、auto-tag 在实际执行前说明真实后果并确认。upload 和所有 mutation 仍需服务端范围预览、结果 diff、审计日志、失败恢复与幂等 key。
3. Candidate review 展示完整回答、来源、冲突、质量理由和最终变更。
4. **已完成当前全站键盘基线**：客户端路由变化后会聚焦目标页 `h1`，九页已通过纯键盘连续旅程并抵达 Query 输入框；Query 输入已使用稳定 name/description，模式选择器已具备 listbox/option、Enter/方向键/Escape 和焦点恢复，历史/收藏已改为具名原生按钮并通过 Enter 重查；Files dialog、Graph D3 与移动导航均有完整定向焦点合同。九页可见按钮在 1024/375px 均有名称。
5. **部分完成**：Files/Compile/Query/Settings/Graph 已建立 375/768/1024px 无页面溢出与移动导航验收，并修复 375px Graph 顶部浮层碰撞；Graph 已新增 120 节点、长标题和移动 bottom sheet 详情验收。其他页面的长表格、长错误和极端本地化文本矩阵仍待补。
6. **部分完成**：零依赖 Chrome DevTools E2E 已成为 CI 门禁，覆盖 Files/Graph、移动导航、九页跨页旅程、Query listbox、Query 历史/收藏的真实键盘操作，九页按钮命名、无失败 reset、低质量 reset、schema enrich、候选 promote/discard、Wiki promote 的确认/取消和 0 mutation；同一隔离浏览器还完成上传、编译轮询、Compile reload/cancel/restart interruption/retry、查询取消/超时/成功、显式贡献、候选确认、401/离线恢复、首次空库、120 节点详情及三档响应式旅程。真实 SDK/Chroma 边界已由独立后端测试覆盖，剩余边界是目标外部厂商和实际 embedding 模型；只有维护收益明确并获得依赖变更授权时再迁移到 Playwright。
7. 每轮视觉修改后检查信息层级、空态、加载态、错误态、键盘和响应式，而不只看截图美观。
8. **新增视觉产品化任务**：重构 Dashboard 的“首次成功/当前风险/下一步”层级；提高正文与辅助文字可读性；把 Settings 拆为访问、模型、可观测性、维护四个清晰区域，并对维护 mutation 增加范围预览与审计入口。

### 退出门禁

- 核心旅程在 clean test workspace 可重复通过且不会触碰真实用户数据。
- 所有高影响 mutation 有确认、审计、失败恢复和 E2E。
- 核心流程可纯键盘完成，375/768/1024px 无主操作遮挡。
- Browser E2E 的安全取消、隔离成功主路径、首次空库、异常恢复、Files/Graph/移动导航、九页跨页标题聚焦、Query listbox/Query 历史与收藏定向键盘操作、九页按钮命名、规模详情和三档响应式已成为 CI 门禁；Computer Use 只用于探索和最终体验验收，不再是唯一回归手段。

## 迭代 5：依赖、性能与开源维护

### 用户结果

维护者可以可信发布、升级、诊断和接受贡献；依赖与性能债务有明确责任边界。

### 工作项

1. 评估 PyPDF2 → pypdf 迁移，消除已弃用解析依赖；升级前建立 PDF 回归语料。
2. **已完成**：Ollama 提供独立 `aiohttp` extra，缺依赖时仅在实际调用点给出可执行提示。
3. 处理 Faiss/SWIG 与 Python 3.13 警告，维护版本兼容矩阵。
4. 清理 stale workflows、占位仓库名、历史完成勾选和失效命令。
5. 建立结构化日志、request/job ID、阶段耗时、provider/向量库健康和可脱敏调试包。
6. 用真实 benchmark 跟踪 retrieval p50/p95、首 token、生成、编译吞吐、Graph 大图和前端 bundle。
7. **部分完成**：文档产品导航、内部资料排除与 strict CI 门禁已完成；隐私、安全、故障排查、升级和 release notes 仍需补齐。
8. 定义代理支持矩阵：普通 HTTP(S) 代理、SOCKS optional extra、`NO_PROXY`、doctor 诊断和无代理回归；测试必须隔离宿主代理，生产不得静默关闭用户代理。
9. 从干净环境重建开发 venv；当前异常 `pytz-2026.2 2.dist-info` 导致 `uv run` 失败，只能作为环境缺陷记录，不能进入 release 证据。

### 退出门禁

- 全量测试不产生项目自身 deprecation/async warning；外部依赖 warning 有已知兼容策略。
- 新贡献者 30 分钟内能运行 fast suite 和前端门禁。
- 每个 release 有 artifact、迁移、回滚、known issues 和 clean-environment smoke。
- 路线图的完成状态只由自动化证据和发布验收决定。

## 推荐执行顺序

1. **发行物可复现**：venv 工具链 → React production image → Docker/clean install smoke。
2. **查询核心安全**：共享 pipeline → contribution POST → provider 预算/断连/隐私合同。
3. **数据真正去重**：canonical storage → dry-run migration → 幂等与统一统计。
4. **真实用户旅程**：写路径安全 → accessibility/responsive → Playwright E2E。
5. **开源维护闭环**：依赖债务 → release/upgrade/rollback → 性能与贡献者体验。

## 每个小迭代的执行合同

1. 选择一个用户可感知结果，先写成功条件、失败条件和不允许触碰的数据。
2. 修改函数/类/方法前执行 GitNexus upstream impact；HIGH/CRITICAL 必须先锁定回归测试并报告风险。
3. 先让能证明缺陷的测试失败，再做最小实现；公共请求、查询核心和迁移必须有合同/幂等测试。
4. 先跑定向验证，再跑 fast/frontend gate；发布合同或共享核心改动跑全量覆盖率与 E2E。
5. 真实浏览器检查加载、空、错、取消、键盘和 375px，不把静态截图当作功能验收。
6. 更新问题 ID、证据、已知风险和回滚方式；未验证的能力不得标记完成。

## 当前下一步

下一步优先完成四个门禁：按发行/配置/查询/存储/前端体验拆分可审查提交后，从 Git artifact 建立完全独立 checkout smoke；把 Compile 的本地单进程 JSON 合同迁移为支持多进程协调、结构化诊断、隔离副本清理和阶段预算的发布级任务仓库；重做 Dashboard 与 Settings 的产品信息架构；为 `standard`/`all` 补干净冷缓存、Linux x86_64、代理与锁文件矩阵。在明确的数据外发授权、脱敏语料和临时目录下，再补目标外部厂商与实际 embedding 模型验证。当前 Compile 精确进度/reload 恢复/真实取消/重启中断历史/失败摘要/retry lineage/200 条终态保留/损坏仓库恢复/常见敏感信息脱敏、隔离写路径、真实 OpenAI SDK/Chroma、浏览器安全与成功主路径、键盘、空态、规模和三档响应式均已完成；最终 Git artifact、跨环境、多进程任务仓库与外部后端矩阵完成前仍不能宣称正式发行可用。
