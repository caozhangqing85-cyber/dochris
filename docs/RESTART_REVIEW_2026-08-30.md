# Dochris 重启全面审查（2026-08-30，更新于 2026-09-02）

## 结论

当前版本判定为 **DEVELOPMENT READY / RELEASE BLOCKED**。

这次重启已经把项目从“主路径不可验证”推进到“开发基线可信”：后端全量测试、覆盖率、fast gate、全仓 lint/format、mypy，以及前端 test/lint/build 均通过；API readiness、查询读写分离、流式查询终止合同、存储迁移 dry-run、全站错误恢复、真实质量门禁和 Graph canonical node 也已建立。

但它还不能被称为优秀开源项目级的可发布产品。React/Nginx、FastAPI、core 与 ChromaDB 已在本机真实 Compose 栈运行并通过健康检查；当前工作树的隔离源码快照也完成了 Python 3.14 安装、CLI、API、前端和测试 smoke。轻量默认安装已经降到 21 个包、约 29 MiB，首次 CLI 使用不再被 Torch/ONNX/Chroma/Kubernetes 阻塞。core/API Docker 分层已完成真实构建和运行验证，严格文档构建也已成为 CI 门禁；LEANN 可选后端的错误包名和过时 API 已修复并完成真实依赖解析。隔离写路径 E2E 已真实执行 upload → compile → query → contribution → promote → quality reset，并修复查询概念字段在晋升时丢失的问题。零新增依赖的 Chrome DevTools 浏览器门禁也已接入 CI：既证明 5 类危险操作取消后产生 0 个 mutation，也通过真实 React UI 完成上传 → 轮询编译 → 查询取消/超时/成功 → 显式贡献 → 候选确认 → 已晋升筛选；401 密钥恢复、持续断网后的手动重试、首次空库、0 节点图谱、120 节点详情、Files 弹窗焦点循环、Graph 键盘打开/关闭、移动导航焦点陷阱、九页纯键盘跨页标题聚焦、Query 模式 listbox、Query 历史/收藏键盘重查，以及九页可见按钮命名审计和 1024/768/375px 核心布局均已自动验证。真实 OpenAI SDK 已通过本地回环兼容端点验证鉴权、请求序列化、非流式与 SSE 流式传输；真实 Chroma PersistentClient 已在临时目录验证写入、排序、元数据更新、重启持久化和删除。真正的发布阻塞已收敛为：尚未从最终提交创建完全独立的 release checkout、`standard`/`all` 仍缺跨平台冷缓存基准、外部厂商端点与实际 embedding 模型尚未进入授权的隔离回归矩阵、存储层历史重复实体只完成安全审计而尚未对真实数据应用迁移。开发可继续，发布不可冒进。

2026-09-02 的三轮 Compile 迭代补齐了最影响真实使用的一组缺陷：服务端现在提供 job ID、精确 processed/success/failed/current files、活动任务复用、刷新恢复、真实取消、终态查询与应用关闭清理；任务历史会原子写入当前工作区，完成/失败/取消任务可跨服务重启恢复，重启时仍处于活动态的任务会明确转为 `interrupted`，保留进度、参数和失败摘要，并可按原参数创建有关联关系和尝试次数的重试。历史默认只保留最新 200 个终态任务且不会裁掉活动任务；损坏 JSON 会先隔离为带 UTC 时间戳的诊断副本，再重建有效空仓库。常见凭据字段、Bearer token、`sk-` provider key 和本机绝对路径会在写盘、API 返回与日志前统一脱敏。前端不再通过 manifest 数量伪造进度或把“停止刷新”冒充取消，新增持久化编译历史、错误详情和重试入口。自动浏览器门禁覆盖 reload、cancel、restart interruption 与 retry；Computer Use 既验证了真实服务重启恢复，也验证了失败卡片和历史卡片只显示 `[REDACTED]` / `<path>`，不含测试密钥、环境变量名或原始私有路径。剩余 P1 已收敛为多进程写入协调、隔离诊断副本清理策略、无法可靠识别的任意无标签秘密、结构化失败详情和阶段预算，不再是“重启即丢失任务上下文”或“历史无限增长”。

审查期间没有提交、重置或覆盖用户原有业务改动：

- `frontend/src/lib/api.ts`
- `src/dochris/api/routes/query.py`

Git 索引原本同时跟踪仅大小写不同的 `.github/PULL_REQUEST_TEMPLATE.md` 和 `.github/pull_request_template.md`，在 macOS clean clone 时发生碰撞。审查已只从索引移除重复的大写路径，保留当前小写中文模板内容；该删除处于 staged 状态，尚未提交。

## 审查范围

- Python CLI、FastAPI、React/Vite、知识编译、Graph、Quality 和查询主路径
- 鉴权、SSE、取消/超时、错误恢复、readiness、质量门禁和数据口径
- 测试隔离、覆盖率、静态检查、CI、Docker、安装与发布合同
- 真实浏览器的九个主页面、离线/重试、慢查询、取消和可访问性风险
- 对照 Open WebUI、AnythingLLM、Khoj、PrivateGPT、Onyx 的工程交付基线

对标重点不是功能数量，而是：首次成功、主路径可追踪、数据可信、安全边界明确、错误可恢复、测试可重复、发行物可安装与升级。

## 最新验证证据

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| 后端全量测试 + 覆盖率 | 通过 | 3252 collected；3206 passed、46 skipped、6 warnings，50.87s；coverage 75.52%，高于 60% 门槛。测试在宿主同时设置 HTTP/HTTPS 与 SOCKS `ALL_PROXY` 时仍通过 |
| 后端 fast gate | 通过 | 354 passed / 2884 deselected |
| Python lint / format | 全仓通过 | `ruff check .` 与 `ruff format --check .` 均通过；338 个 Python 文件格式一致，benchmark/examples 已纳入同一门禁 |
| Python typecheck | 通过 | mypy 检查 141 个源码文件，无错误 |
| 前端单元/合同测试 | 通过 | 56 tests passed；新增 compile 历史、服务中断终态、失败详情与 retry API/UI 合同，并保留活动状态、精确百分比、网关密钥恢复、Query、键盘、质量门禁和确认合同 |
| 前端 lint / production build | 通过 | ESLint 通过；Vite 完成 2788 modules 构建 |
| 隔离浏览器 E2E | 通过（安全、成功、恢复、空态、规模、键盘、响应式） | production build 由真实 headless Chrome 渲染；Compile 旅程覆盖活动 job 跨页/reload 恢复、真实 cancel、服务重启中断历史、错误展示和有关联 retry 完成，并保留 Files/Graph/移动导航/九页键盘、5 类高影响操作 0 mutation、上传→编译→查询→贡献→晋升、401/离线恢复、首次空库、120 节点图谱及 1024/768/375px 验收。不触碰真实知识库、凭据或 provider；CI 执行 `npm run test:e2e` |
| API 启动 | 通过 | `make web-api` 在 `127.0.0.1:8000` 启动；embedding preload 成功 |
| `/health` / `/ready` | 通过 | 最新后端进程存活；workspace 与必需目录存在且可写 |
| 本地无匹配查询 smoke | 通过 | `mode=concept` 对 `zzzz-no-match-01a0518d` 返回空结果、`answer=null`、10ms；未调用 provider |
| `/api/v1/status` | 通过 | 5 manifests、4 compiled、1 promoted；默认最低质量分为 85 |
| `/api/v1/graph` | 通过 | 28 concept、5 source、5 summary、61 edges；无 `_N` 后缀节点 |
| 存储重复 dry-run | 通过 | 扫描 59 文件；5 个精确编号副本可安全迁移，16 个跨层/source/symlink alias 受保护只报告 |
| Docker Web/Compose | 通过（本机 arm64） | core、API、Chroma、Web 四服务均 healthy；`/ready`、`/healthz`、SPA fallback 与 `/api` proxy 均有真实 HTTP 证据 |
| Docker 镜像运行时 | 通过 | core 65.46 MB（较旧约 772 MB 减少约 91.5%），API 523.60 MB，Web 约 22 MB；API 为 `torch 2.13.0+cpu` 且 CUDA=false，core 不再安装 Torch |
| Python release artifact | 轻量基线通过（当前工作树隔离 smoke） | Python 3.14.6 从当前 wheel 安装基础包共 21 个依赖，warm-cache 0.221s、venv 约 29 MiB；无 MarkItDown、ChromaDB、sentence-transformers、Torch、ONNXRuntime 或 Kubernetes。`kb init --non-interactive PATH`、`kb doctor`、`kb version` 与空库查询均通过。历史 `.[dev,api,pdf]` 全量基线为 146 包、40m10s、约 1.2 GiB；`standard` 的干净冷缓存基准仍待补 |
| 隔离 API 配置 | 通过 | 显式临时 `WORKSPACE` 启动 API 后 `/ready` 与 `/api/v1/status` 均指向临时工作区；不会读取 home `.env` 或泄漏 home provider 配置 |
| 隔离关键写路径 E2E | 通过（确定性边界） | 子进程先设置临时 `HOME`/`WORKSPACE` 再导入应用；真实 API 路由、解析、manifest、编译持久化、查询检索、显式贡献、候选晋升和质量重置全链执行。只替换外部 LLM 与向量后端，未访问真实知识库或凭据 |
| 隔离真实后端边界 | 通过（本地确定性边界） | 真实 OpenAI SDK 对仅绑定回环地址的兼容 fixture 完成鉴权头、消息序列化、非流式响应、SSE chunk 与关闭验证；真实 Chroma PersistentClient 在独立子进程和临时目录完成写入、余弦排序、metadata 更新、SQLite 重启持久化与删除。没有调用外部厂商、真实 embedding 模型或用户数据 |
| 前端 clean install | 通过（有工具链约束） | 隔离源码快照 `npm ci`、40 tests、lint、2787-module build 通过；Node 23 的 ESLint engine 警告已通过 `.nvmrc` 与 `engines.node >=22.13 <23` 固化到 Node 22 |
| LEANN 可选后端 | 通过合同与依赖解析 | 修正不存在的 `leann-vector` 为官方 `leann>=0.3.7`；适配 builder/searcher 0.3.x API、旧注册表迁移、metadata/delete/list 合同；全新 Python 3.13 环境成功解析 139 个包。PyPI 当前由元包 0.3.7 解析到 core/backend 0.3.4，因此查询时把 `recompute_embeddings` 放在 0.3.4 与新版均兼容的 `search()` 调用上 |
| 文档发布 | 通过 | 最新 `mkdocs build --strict` 成功、1.35s；Material 输出 MkDocs 2.0 未来兼容性提示，但未产生 strict 构建 warning；CI 已将真实 warning 作为发布失败 |
| GitNexus 变更影响 | CRITICAL（已知） | 2026-09-02 最新全工作树检测为 960 changed symbols、155 changed files、261 affected processes；这是整个重启工作区的累计范围，必须按发行、配置、查询、存储、前端体验等边界拆成可审查提交，不能一次性视为低风险提交 |
| 当前构建浏览器复验 | 通过（隔离临时工作区） | 2026-09-02 用 Computer Use 检查 Dashboard、Files、Compile、Query、Status、Settings 的加载和空态；随后在 `/tmp/dochris-compile-restart-review.*` 预置活动 job，真实启动、停止并重新启动 API，确认 Compile 显示“服务中断”、原进度、参数、`ServiceRestart` 摘要、重试入口，并在空库重试时正确显示“没有待重试的文档”。本轮又在 `/tmp/dochris-sanitized-history-review.*` 生成包含测试 Bearer key、API key 字段和 `/Users/...` 路径的真实失败 job；Compile 当前卡片和历史卡片只显示 `RuntimeError: [REDACTED] ... <path>`，Chrome AX 检查确认三类原文均不存在。未访问真实知识库或 provider；视觉信息架构问题仍保留 |
| 本轮交互与可访问性修复 | 自动化浏览器主路径与 Computer Use AX 热复验通过 | Files 详情具备完整 dialog/focus 合同；关闭的移动侧栏退出 Tab 与语义树，打开后锁定背景、循环焦点并返回菜单按钮；客户端路由变化后聚焦新页面 `h1`，九页可由真实 Tab/Shift+Tab/Enter 连续访问并抵达 Query 输入框；Query 模式选择器具备 listbox/option 语义、Enter/方向键/Escape 和焦点恢复，历史/收藏条目已改为具名原生按钮并由 Enter 真实触发查询；九页可见按钮在 1024/375px 均有名称。55 项合同测试和隔离 Chrome 安全/成功/键盘旅程均通过；2026-09-02 又以临时工作区复查 Dashboard、Files、Compile、Query、Status、Settings 的加载与空态。Computer Use 的焦点摘要仍报告外层 HTML，而 CDP DOM 断言确认实际 active element 为目标 `h1`，该工具差异保留为已知观察项 |

## 真实体验记录

1. Dashboard、Files、Compile、Query、Candidates、Quality、Graph、Status、Settings 均可打开；主要数据页已统一错误分类、诊断和重试。
2. 缓存查询样本耗时 0.2 秒。一次非缓存查询总耗时 31.6 秒，其中本地检索 0.1 秒、provider 首 token 30.5 秒、生成阶段 31.4 秒。主要延迟来自外部 provider，不是本地检索。
3. Query 支持取消和总超时；真实 Chrome 中取消后回到 idle，不保留部分答案、耗时、贡献回执或历史。后端 SSE 对成功、超时、异常保证恰好一个终止事件，客户端取消重新抛出 `CancelledError`。
4. Settings 在后端关闭时会显示“后端网关不可用”及代理目标；后端恢复后点击“重试”可重新加载配置。共享重试按钮曾把 React click event 误传给加载函数，已修复并有回归测试。
5. Quality 不再用编译率冒充质量。默认最低质量分提升到 85，`quality_gate` 现在是自动晋升、CLI 和 HTTP 晋升的硬门禁，并记录实际分数和阈值；Compile 使用服务端动态阈值，低分条目显示禁用原因。
6. Graph 已在构图层合并 canonical 概念：当前 28 个概念节点，不再出现 `量子比特_1` 一类展示重复。历史文件和 manifest 仍保留重复/变体，因此 Status 仍诚实显示 38 个“概念文件”和 11 个“摘要文件”。
7. 文件详情弹窗已补完整 dialog/focus 合同；Graph 节点已有 roving tabindex、Enter/Space、方向键、Escape 和焦点恢复；移动导航关闭时不再把屏幕外控件留在 Tab 顺序，打开后锁定背景并循环焦点；客户端路由切换后会聚焦新页 `h1`，Dashboard、Files、Compile、Candidates、Quality、Graph、Status、Settings、Query 九页已由纯键盘连续访问并抵达查询输入框；Query 模式选择器已有 listbox/option、Enter/方向键/Escape 和焦点恢复，历史/收藏条目也已改为具名原生按钮并通过 Enter 重查。以上均由真实 CDP 键盘事件验证，且九页可见按钮在 1024/375px 均有名称。Graph 默认标签/边可读性仍未达产品级。
8. Settings 现在把 Dochris 网关访问密钥与 LLM provider key 明确分开；即使首次加载因 401/403 失败，网关密钥恢复卡片仍可使用。默认 Compose 只绑定 `127.0.0.1` 并显式启用本机无认证模式；配置 `DOCHRIS_API_KEY` 后仍强制校验。
9. 本轮没有对真实知识库执行 upload、promote、reset、schema enrich、auto-tag 或 storage migrate `--apply`。upload、compile、query、contribution、promote 和 reset 已在临时隔离工作区完成确定性 API E2E；隔离浏览器已覆盖上传 → 编译 → 查询取消/超时/成功 → 贡献 → 候选晋升、401 密钥恢复、持续离线重试、首次空库、0 节点图谱、120 节点详情、Files/Graph/移动导航/Query listbox/Query 历史与收藏定向键盘旅程、九页跨页纯键盘旅程、九页按钮命名审计与 1024/768/375px 核心布局。真实 SDK/存储边界已由回环 OpenAI 兼容 fixture 和临时 Chroma PersistentClient 覆盖；真实数据操作仍缺少服务端范围预览、结果 diff、统一审计/恢复，外部厂商端点与实际 embedding 模型仍待授权验证。
10. 一次使用随机字符串的 SSE 冒烟因短词 `no` 误命中 `CNOT`，意外把“量子门”检索上下文发给当前配置的 BigModel provider，provider 返回 200；没有发生知识写入。随后已增加强关键词证据过滤并用测试复现，最新安全 `concept` smoke 返回空结果且没有 provider 调用。此事件说明外发前仍需要显式隐私确认与服务端策略门禁。
11. clean install 的 `kb init PATH` 曾忽略显式路径，转而命中已缓存的默认 home workspace；沙箱阻止了实际 home 写入。现已让显式路径成为真实隔离边界，并增加回归测试。
12. 非交互初始化曾打印 API key 前缀；现在只记录“已提供（已隐藏）”，测试保证日志不包含任何 key 片段。
13. 显式 `WORKSPACE` 曾仍从 home `.env` 加载 model/provider 配置；现在只查显式 workspace 与当前目录，不再回退到 home secret。隔离 API 实测 `has_api_key=false` 且模型来自临时 workspace。
14. 历史完整 API/PDF/dev 安装一次拉取 146 个包，含 Torch、ONNX、Kubernetes 等重依赖；40m10s 与约 1.2 GiB venv 是真实首次使用障碍。当前已拆成轻量基础、`standard` 与按能力 extras；基础 wheel 实测 21 包、约 29 MiB，warm-cache 0.221s。
15. `all` extra 原先依赖 PyPI 不存在的 `leann-vector`，导致任何解析都直接失败；即使绕过依赖，适配器仍使用过时的 `build_index(path, chunks)`、错误的 metadata 路径和搜索参数。现已改为官方 `leann` 包与 0.3.x API，并用旧注册表迁移、重建、删除、查询和真实解析证据锁定。
16. 文档站原先严格构建产生 32 个 warning，包括错误导航路径、两处无法解析的 API docstring 与无关归档资料断链。产品文档导航已修正，内部资料保留在仓库但不进入公开站点，CI 改为严格构建。
17. 查询 API 的概念结构使用 `title/content`，候选晋升却只识别 `name/explanation`，导致查询衍生候选晋升后静默丢失概念文件。隔离写路径 E2E 首次稳定复现该缺陷；贡献边界现会归一化两套字段并保留来源元数据，单元合同、102 项相关测试和全量回归均通过。
18. Query 首次渲染时以“暂无已编译文件”作为动态 placeholder，Chrome 的辅助技术树在异步加载 5 个文档后仍保留错误名称。文本框现使用稳定名称“查询知识库”，并通过 live status 描述加载态和可查询数量；Computer Use 已在当前构建复验。
19. `/api/v1/promote` 曾绕过 CLI 已使用的 `quality_gate`，前端也对 69/77/78/82 分条目显示可执行按钮。HTTP 路由现在先执行完整质量门禁，失败时不调用底层晋升；Compile 按 `/status` 的动态阈值禁用低分操作并解释原因。
20. 新增的真实 Chroma 测试定向运行通过、全量运行却返回空 collection；根因不是存储实现，而是旧 `test_index_knowledge.py` 在 pytest 收集阶段永久替换 `sys.modules["chromadb"]`。真实后端验证现进入独立子进程，包含污染源的 59 项顺序回归与 3244 项全量套件均通过。
21. Compile 过去返回“已提交”后，前端通过 manifest 总数估算进度；“停止刷新”只停本地 polling，不会停止模型调用。现在服务端持有任务、返回 job ID 和精确计数，重复提交复用活动 job，页面刷新后恢复同一 job，取消会取消真实 `asyncio.Task`，应用 shutdown 会等待任务收尾。
22. 新 job 合同首次让隔离写路径 E2E 暴露旧同步假设：测试在 `accepted` 后立刻读取 manifest。它现按 job ID 等待 `completed`，同时断言 processed/compiled/failed 后再验证 summary、concept 和 manifest。
23. 宿主机同时设置 HTTP/HTTPS proxy 与 SOCKS `ALL_PROXY`，但开发依赖只安装普通 `httpx`；原全量套件有 14 项在客户端构造时因缺少 `socksio` 失败。测试 fixture 现在清除大小写两套 proxy/no-proxy 变量，3198 项在原宿主环境下通过。生产运行仍尊重用户代理；SOCKS 可选依赖和文档尚未定义，不能误报为已支持。
24. Computer Use 的隔离空库实测确认导航、禁用态和首次引导可用，但视觉仍有明显产品差距：大面积留白、正文和辅助文字偏小偏淡、Dashboard 只展示数字和配置、Settings 把网关密钥、可观测性、维护 mutation 与 LLM 配置纵向堆叠。下一阶段应先重做信息架构和证据层级，再做装饰性视觉优化。
25. Compile job 原先只存在进程内存，服务重启后历史和失败上下文消失。现在每次状态变化都会原子写入工作区 `data/compile-jobs.json`；重启加载会把未完成任务标记为 `interrupted` 而不是伪装完成，并保留 processed/compiled/failed、原并发/limit、错误、时间戳和 retry lineage。历史默认最多保留 200 个终态任务并保留所有活动任务；损坏 JSON 会隔离后重建；常见 secret/token/key 与私有绝对路径会在持久化、API 和日志前脱敏，后台失败日志不再输出原始 traceback。单元/API、自动 Chrome 和两次 Computer Use 真实运行均已验证。当前 JSON 仓库仍假定单服务进程；损坏副本尚无自动清理策略，任意无标签秘密也无法仅靠正则可靠识别。

## 已解决的高风险问题

| 问题 | 当前状态 | 关键证据 |
| --- | --- | --- |
| 前端语法错误、鉴权边界分裂 | 已解决 | JSON、SSE、upload、metrics 共用鉴权头；test/lint/build 全绿 |
| 后端红色基线和不可信测试 | 已解决 | 全量 3206 passed；测试不再读取真实 home 配置、宿主代理或写真实用户目录；真实 Chroma 验证使用独立子进程隔离全局模块 mock |
| mypy 和 CI 漏检前端 | 已解决 | mypy 141 source files；CI 增加 frontend test/lint/build |
| 无效 `web` extra 和旧启动合同 | 已解决 | 官方开发入口统一为 `make web-api` + `make web` |
| SSE 错误/取消/终止合同不稳定 | 已解决 | 稳定 code、trace ID、脱敏错误、阶段耗时和单终止事件均有测试 |
| 页面把错误显示为空数据 | 已解决（九个主页面） | 401、timeout、gateway、server、protocol 可分类并可重试 |
| Quality 结论与证据矛盾 | 已解决语义 | 评分、编译覆盖率、达标率分离；85 分硬门禁 |
| Graph `_N` 展示重复 | 已解决构图层 | 28 canonical concepts、61 edges、无 `_N` label |
| FastAPI `on_event` 弃用 | 已解决 | 迁移 lifespan；严格 DeprecationWarning 定向测试通过 |
| async 测试实际上未执行 | 已解决 | 使用 `IsolatedAsyncioTestCase`；暴露并修复真实重试缺陷 |
| transient provider 错误绕过 retry | 已解决 | `RetryManager` 先捕获后按 `should_retry` 分类；最后一次失败不再多睡眠 |
| Makefile 命中系统开发工具 | 已解决 | pytest/ruff/mypy/pip/build 均通过项目 `$(PYTHON)`；`make check` 和 typecheck 复验通过 |
| React 未定义 production image | 已解决并实机验证 | Node 22 build + Nginx SPA/API proxy + Compose web service；本机镜像 build、四服务 healthy 与 HTTP smoke 通过 |
| Debian Trixie 已移除 `libgl1-mesa-glx` | 已解决 | runtime 改用 `libgl1`，并以分发合同测试防回归 |
| core/API 重复执行 apt 且网络抖动即失败 | 已解决基础层 | `BUILD_TARGET` 后移以复用系统层；apt 增加 3 次重试 |
| CPU 服务镜像误拉 CUDA Torch | 已解决 | 依赖安装前固定 PyTorch CPU wheel；镜像内确认 `2.13.0+cpu` 与 CUDA=false |
| Chroma 健康检查依赖不存在的 curl 与已废弃 v1 endpoint | 已解决 | 改用 Bash `/dev/tcp` 请求 `/api/v2/heartbeat`，容器实际 healthy |
| API upload 路由缺 `python-multipart` | 已解决 | `api` extra 补依赖；镜像内确认 0.0.32，API actual ready |
| Web healthcheck 的 localhost 解析到 IPv6 | 已解决 | 探针固定 `127.0.0.1/healthz`，Web 容器实际 healthy |
| 默认 Compose Web 通过代理访问 API 返回 403 | 已解决本机路径 | 默认端口仅回环绑定并显式启用本机模式；Settings 增加独立网关密钥与鉴权失败恢复入口 |
| Python wheel/metadata 未验证 | 已解决 | sdist/wheel 构建与隔离安装通过；SPDX `MIT` 和 setuptools 77 合同消除 2027 弃用警告 |
| 普通查询与流式查询检索逻辑漂移 | 已解决核心阶段 | retrieval 与 rerank 共用实现；SSE 会真实执行 reranker 并报告阶段耗时 |
| GET 查询可隐式写 contribution | 已解决 | GET 始终只读；候选贡献改为独立认证 `POST /api/v1/query/contribution`，UI 分两步执行 |
| 随机多词查询短片段误命中 | 已解决 | 单个偶然短片段不再构成匹配证据；143 个查询域测试与最新 HTTP smoke 通过 |
| 晋升重试制造 `_1/_2` 副本 | 已解决新写入 | 内容完全相同时复用已有文件；不同内容继续保留版本冲突语义；相关链路 40 tests 通过 |
| 历史重复文件无迁移合同 | 已解决工具合同 | 新增 `kb storage audit/migrate/rollback`；默认 dry-run、精确哈希、备份 manifest、冲突拒绝覆盖 |
| `kb init PATH` 忽略显式工作区 | 已解决 | 显式路径直接解析并刷新 Settings；不会因缓存落入默认 home workspace；定向与全量测试通过 |
| 初始化日志暴露 key 前缀 | 已解决 | 非交互路径仅输出已隐藏状态；回归测试禁止 key 或前缀进入输出 |
| 显式 `WORKSPACE` 仍读取 home `.env` | 已解决 | `WORKSPACE` 成为配置隔离边界；两个回归测试与隔离 API `/status` smoke 通过 |
| Git 大小写路径冲突 | 已解决索引合同 | 移除重复大写 PR 模板索引项，保留小写中文模板；分发测试拒绝 case-insensitive 路径碰撞 |
| Node 版本只存在于 CI/Docker | 已解决合同 | `.nvmrc=22`、package `engines`、README/Quickstart/安装文档统一要求 Node 22.13+ 且不支持 Node 23 |
| 默认安装被向量/ML/文档重依赖拖慢 | 已解决轻量合同 | 基础依赖只保留 CLI/关键词能力；`documents`、`vector`、`standard` 与其他能力 extras 独立；隔离 wheel 为 21 包、约 29 MiB，重依赖均未出现 |
| Ollama 可选依赖导入时告警且提示不可执行 | 已解决 | 新增 `ollama` extra；普通导入保持安静，真正调用时明确提示安装 `dochris[ollama]`；相关 30 tests passed、6 skipped |
| LEANN extra 无法安装且运行时 API 过时 | 已解决 | 使用官方 `leann>=0.3.7`；23 个分发/适配器合同测试通过，Python 3.13 clean resolver 成功解析 139 包 |
| Docker core/API 体积相同且构建网络脆弱 | 已解决本机基线 | core 65.46 MB、API 523.60 MB；BuildKit pip cache、apt/pip retry、CPU-only Torch、stdlib readiness probe 均有镜像/容器实证 |
| API 启动隐式访问 Hugging Face | 已解决默认路径 | embedding preload 默认关闭，仅在 `DOCHRIS_PRELOAD_EMBEDDING=true` 时启用；空容器启动日志不再产生网络失败噪声 |
| 文档站 warning 未阻断发布 | 已解决 | 严格构建 0 warning；CI 执行 `mkdocs build --strict`，内部/归档资料不会污染产品站点 |
| 查询候选晋升静默丢失概念 | 已解决 | API `title/content` 在贡献边界归一化为 `name/explanation`；隔离全链路 E2E 验证晋升后的 summary 与 concept 文件均存在 |
| Query 异步加载后读屏名称残留空态 | 已解决 | 稳定 `aria-label` + live availability status；前端合同与当前 Chrome AX 树均通过 |
| HTTP 晋升绕过质量门禁 | 已解决 | `/promote` 在复制前执行 `quality_gate`；低分时返回明确原因且底层晋升未调用，API 9 项定向测试和全量回归通过 |
| Compile 低分条目仍展示可执行晋升 | 已解决 | 使用服务端动态阈值；当前 69/77/78/82 分按钮均在 Chrome AX 树显示 disabled 和具体门槛原因 |
| 375px Graph 搜索与视图切换器重叠 | 已解决 | 隔离 Chrome 首次稳定复现浮层区间重叠；小屏将切换器移到搜索框下方，375/768/1024px 布局门禁均通过 |
| 空库仍可触发无效重编译且 Graph 显示空白画布 | 已解决 | Compile 按服务端 `stale_count` 禁用并前置保护 no-op 写入；0 节点 Graph 显示首次使用引导，隔离 Chrome 证明 0 mutation |
| 375px Graph 节点详情越界且关闭控件无可访问名称 | 已解决 | 120 节点/长标题场景首次测得详情范围 `left=98, right=418`；移动端改为图谱内 bottom sheet，并补充区域与关闭按钮语义后通过边界和关闭验收 |
| 跨页面纯键盘矩阵只覆盖三页 | 已解决 | 隔离 production build 已用真实 Tab/Shift+Tab/Enter 连续访问九页；每次 SPA 路由切换均聚焦目标 `h1`，最终可继续抵达 Query 输入框，且 0 mutation |
| Compile 使用估算进度且取消只停止刷新 | 已解决单进程持久化合同 | 服务端 job ID、精确进度、活动任务复用、reload 恢复、真实取消、shutdown 清理、原子历史、重启中断恢复、retry lineage、200 条终态保留上限、损坏仓库隔离重建和常见敏感信息脱敏均有单元/API/自动浏览器与 Computer Use 实证；多进程协调、隔离副本清理、结构化诊断和阶段预算仍列为 P1 |
| pytest 被宿主代理环境污染 | 已解决测试隔离 | fixture 清理大小写 HTTP/HTTPS/ALL/NO proxy；原环境下 3206 passed，真实回环 OpenAI SDK 和隔离子进程写路径均通过 |

## 当前问题台账

### P0 — 发布阻断

| ID | 问题 | 影响 / 退出证据 |
| --- | --- | --- |
| RST-P0-102 | 最终提交的独立 release checkout 仍未验证 | 当前工作树隔离快照已完成 Python 3.14 全依赖安装、CLI、API、前端与定向测试；`git ls-files` 已确认 `frontend/e2e/smoke.mjs` 与两份重启审查/路线图仍未纳入 Git，当前成功不能代表 `HEAD` 或 release archive。提交拆分完成后必须从 Git artifact 重新 clone 并运行统一 smoke |
| RST-P0-106 | 外部厂商与实际 embedding 模型边界仍不完整 | 浏览器 fixture 主路径、真实 OpenAI SDK 回环传输和真实 Chroma PersistentClient 持久化均已自动验证；仍需在明确的数据外发授权、脱敏语料和临时目录下验证目标厂商的真实协议差异、首 token/取消/限流，以及实际 embedding 模型的加载、维度、性能和重启兼容性 |

### P1 — 核心体验、数据与维护性

| ID | 问题 | 影响 / 建议 |
| --- | --- | --- |
| RST-P1-101 | provider 首 token 样本为 30.5 秒 | 增加首 token/总预算、取消传播、降级和 provider 统计；不能把外部延迟混入本地性能 |
| RST-P1-102 | 真实存储仍有 5 个可迁移编号副本 | dry-run、备份和回滚合同已完成；真实 `--apply` 未执行，source variant 与跨层 replica 仍需统一身份模型 |
| RST-P1-103 | compile job 持久化仍是单进程 JSON 合同 | 当前工作区已有原子历史、重启中断恢复、失败摘要、参数/时间戳、retry lineage、200 条终态保留上限、损坏仓库隔离重建和常见 secret/path 脱敏；仍需多 worker/多实例写入协调、隔离诊断副本清理策略、结构化失败详情下载、无法识别秘密的安全边界和阶段预算。生产多进程前应迁移到 SQLite/队列或提供文件锁与单 worker 强约束 |
| RST-P1-104 | 高影响操作缺统一预览/diff/审计/恢复 | Files/Quality 无目标时禁用 reset；Files/Quality reset、Compile/候选晋升、候选永久丢弃、enrich、auto-tag 已说明真实后果并确认。后端仍缺统一 dry-run 范围、结果 diff、幂等键、审计和失败恢复合同 |
| RST-P1-105 | Graph 默认信息密度和交互不足 | 标签、边、筛选空态、键盘替代列表、聚类和大图降级仍需产品化 |
| RST-P1-106 | API key 仍是单共享密钥模型 | 本机首次使用与浏览器配置已可用；多用户/公网模式仍缺轮换、撤销、权限与服务端会话模型 |
| RST-P1-109 | PDF 解析仍依赖已弃用的 PyPDF2 | 全量测试剩余警告之一；应评估迁移到维护中的 `pypdf` |
| RST-P1-110 | Docker/依赖仍缺跨平台锁定 | 本机已完成 BuildKit 下载缓存、重试、CPU-only Torch 与分层镜像；但 Linux x86_64/WSL、干净 registry cache 和锁文件仍未验证 |
| RST-P1-111 | 推荐完整安装尚无干净冷缓存基准 | 轻量默认已降到 21 包、约 29 MiB；仍需对 `standard`/`all` 建立 cold/warm 时间、空间、锁文件和跨 Python/OS 基准，避免把基础安装改善误报为完整产品首次成功 |
| RST-P1-112 | SOCKS 代理支持合同未定义 | 生产 httpx 尊重宿主代理，但普通依赖不含 `socksio`；需要明确 optional extra、doctor 诊断、错误文案与 HTTP/SOCKS/no-proxy 测试矩阵，不能静默禁用代理 |

### P2 — 可访问性与开源交付

| ID | 问题 | 影响 / 建议 |
| --- | --- | --- |
| RST-P2-102 | 其他页面的响应式长内容矩阵仍不足 | Graph 已用 120 节点、长标题和移动 bottom sheet 完成 375px 详情验收；Files/Compile/Query/Settings/Graph 基线也覆盖 375/768/1024px，剩余风险转为其他页面的长表格、长错误和极端本地化文本 |
| RST-P2-103 | UI 视觉语义偏通用模板 | 隔离 Computer Use 实测显示大面积留白、弱对比小字号与过长 Settings；来源、编译、信任、质量和下一步没有形成明确产品层级 |
| RST-P2-104 | 发布、升级、回滚和支持矩阵不完整 | 新用户/贡献者难以判断兼容性和恢复路径 |
| RST-P2-105 | stale workflow 与路线图完成状态仍需清理 | 自动化和文档不能作为当前事实来源 |

## 剩余技术警告

- 全量套件剩余 6 条 warning，主要来自 Faiss/SWIG 的 Python 3.13 deprecation 和 PyPDF2 弃用；已不再包含 FastAPI `on_event` 或未 await 的项目 async 测试警告。
- Docker 已在本机 arm64 daemon 真实 build/run；core 为 65.46 MB、API 为 523.60 MB。x86_64、Windows/WSL、Linux 主机和干净 registry cache 尚未验证。
- LEANN 元包 0.3.7 依赖解析会扩展到 139 个包，并在当前 PyPI 元数据下选择 core/backend 0.3.4；安装可解且适配器合同兼容，但仍属于重型实验能力，尚未完成真实向量构建/查询 benchmark，不应成为默认安装。
- 当前环境没有安装 Bandit；安全扫描没有被误报为通过。
- 当前 `.venv` 存在异常的 `pytz-2026.2 2.dist-info` 元数据目录，导致 `uv run` 解析版本失败；本轮使用 `.venv/bin/python` 完成门禁。最终 release checkout 必须从干净环境重建，不能修补后继续把当前 venv 当发行证据。
- SOCKS 代理尚无安装 extra/doctor 合同；测试隔离已修复，但生产支持状态仍是“未定义”，不是“已验证”。
- Compile 历史当前使用工作区 JSON 原子替换，适合本地单进程；正常历史已限制为最新 200 个终态任务，损坏仓库会隔离重建，常见 secret/path 已在写盘、API 与日志前脱敏。多 worker/多实例并发写入、隔离副本清理、任意无标签秘密和结构化诊断仍未形成发布合同。
- 项目全仓 `ruff check .` 与 `ruff format --check .` 已通过；benchmark/examples 不再是门禁盲区。
- 当前构建已完成九页只读 Computer Use 验收；隔离 Chrome CI gate 同时验证 5 页安全取消、Files/Graph、移动导航、九页跨页标题聚焦、Query listbox、Query 历史/收藏的真实键盘操作、九页按钮命名、上传→编译→查询取消/超时/成功→贡献→候选晋升、401/离线恢复、首次空库、120 节点详情与三档核心布局。另有真实 OpenAI SDK 回环传输和真实 Chroma PersistentClient 自动测试；这些证据仍不等于目标外部厂商或实际 embedding 模型的生产验证。

## 根因归纳

1. Web 从旧单命令界面迁到 React/Vite 后，启动、镜像、认证、CI 和文档没有同步完成。
2. 业务能力按入口重复实现，普通查询和流式查询因此长期漂移。
3. 数据层用文件名冲突后缀解决写入碰撞，却没有 canonical identity、alias 和迁移合同。
4. 路线图曾以“功能存在”代替“可重复安装、验证、恢复和发布”。
5. 测试数量很多，但此前存在真实 home 污染、async 测试未执行、慢套件无分层等可信度问题。

## 审查边界

- 没有改写用户 home 配置，也没有为了让默认阈值生效而覆盖现有个人配置。
- 除上文已披露的误命中 SSE 冒烟外，没有主动执行真实外部问答；后续真实问答与真实知识库写入需单独的数据外发/写入授权。
- upload、compile、contribution、promote 和 reset 只在临时隔离工作区执行；没有对真实知识库执行这些操作，也没有执行 schema enrich、auto-tag 或 storage migrate `--apply`。
- Docker 仅在当前 macOS arm64 环境通过；没有对 Windows/WSL、Linux、多用户或公网环境宣称通过。

## 对标参考

- [Open WebUI 文档](https://docs.openwebui.com/)：快速开始、安全边界与扩展说明。
- [AnythingLLM 文档](https://docs.anythingllm.com/)：桌面/自托管边界、日志、隐私和部署结构。
- [Khoj 文档](https://docs.khoj.dev/)：个人知识库、自托管、隐私和多端同步。
- [PrivateGPT 文档](https://docs.privategpt.dev/introduction)：RAG/API 分层、配置和可观测性。
- [Onyx 文档](https://docs.onyx.app/welcome)：权限、发布流程和工程化基线。
