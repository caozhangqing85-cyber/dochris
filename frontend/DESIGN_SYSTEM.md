# Dochris 前端设计系统实施总结

> 基于 OpenDesign 本地设计服务 Notion 设计系统，面向知识库阅读场景的全盘前端重构

## 1. 设计流程

### 1.1 OpenDesign 服务联动

| 步骤 | 操作 | API 端点 |
|------|------|---------|
| 连通验证 | 探测 daemon 服务 | `GET http://127.0.0.1:56332/` |
| 技能发现 | 列出 151+ 设计技能 | `GET /api/skills` |
| 设计系统检索 | 筛选知识库相关系统 | `GET /api/design-systems` |
| Notion 系统获取 | 获取完整设计规范 | `GET /api/design-systems/notion` |
| Mintlify 系统获取 | 获取阅读优化规范 | `GET /api/design-systems/mintlify` |
| Clean 系统获取 | 获取极简风格规范 | `GET /api/design-systems/clean` |
| AI 设计生成 | 通过 Claude agent 生成设计分析 | `POST /api/chat` (agentId: "claude", designSystemId: "notion") |

### 1.2 设计系统选型

从 OpenDesign 的 151 个设计系统中筛选出 3 个参考系统：

- **Notion**（最终采用）— 温暖极简主义、暖灰 #f6f5f4 侧栏、Notion Blue #0075de、4px 按钮圆角、9999px 药丸徽章、多层阴影堆叠
- **Mintlify** — 文档平台、阅读优化、Inter 字体 + 紧凑字距
- **Clean** — 极简聚焦、充足留白

最终方案以 Notion 设计系统为主框架，严格遵循其所有设计令牌。

## 2. Notion 设计令牌体系

### 2.1 核心令牌

| 令牌 | 值 | 说明 |
|------|-----|------|
| `--color-primary` | `#0075de` | Notion Blue |
| `--bg-sidebar` | `#f6f5f4` | 暖白侧栏 |
| `--bg-card` | `#ffffff` | 纯白卡片 |
| `--text-primary` | `rgba(0,0,0,0.95)` | 近黑文字 |
| `--border-default` | `rgba(0,0,0,0.1)` | 耳语级边框 |
| `--radius-lg` | `12px` | 卡片圆角 |
| 按钮圆角 | `4px` | Notion 标准按钮 |
| 输入框边框 | `1px solid #dddddd` | Notion 标准输入 |
| 药丸徽章圆角 | `9999px` | Notion pill badges |
| 字体 | Inter | `font-feature-settings: "lnum" 1, "locl" 1` |
| 字重体系 | 400/500/600/700 | 4 级字重 |

### 2.2 Notion 多层阴影

```css
--shadow-sm: 0 4px 18px rgba(0,0,0,0.04), 0 2px 7.85px rgba(0,0,0,0.027);       /* 2 层 */
--shadow-md: 0 4px 18px rgba(0,0,0,0.04), 0 2px 7.85px rgba(0,0,0,0.027), ...;   /* 3 层 */
--shadow-lg: 0 0 0 1px rgba(0,0,0,0.03), 0 4px 18px ..., 0 2px 7.85px ..., ...;   /* 5 层 */
```

每层单独透明度 ≤ 0.05，累积产生自然深度感。

## 3. 逐页重构清单

### 3.1 共享 UI 组件（6 个）

| 组件 | 关键变更 |
|------|---------|
| `StatCard.tsx` | 12px 圆角 + `--shadow-sm`、`letterSpacing: '-0.25px'` |
| `PageHeader.tsx` | `letterSpacing: '-0.625px'`（Notion sub-heading）、字重 700/400 |
| `SectionHeader.tsx` | `letterSpacing: '0.125px'`（Notion badge tracking）、字重 600 |
| `EmptyState.tsx` | 标题字重 600、描述字重 400 |
| `Badge.tsx` | `borderRadius: 'var(--radius-full)'`（9999px 药丸）、`letterSpacing: '0.125px'` |
| `AppLayout.tsx` | 侧栏 240px、`--bg-sidebar: #f6f5f4`、4px 按钮圆角导航 |

### 3.2 页面组件（8 个）

| 页面 | Notion 设计元素 |
|------|----------------|
| `DashboardPage.tsx` | 快捷操作卡片 hover 阴影过渡、配置标签大写 + 0.125px tracking |
| `FilesPage.tsx` | `btnPrimary`（4px 圆角、8px 16px padding、#0075de）、输入框 `#dddddd` 边框、状态药丸徽章 9999px、Modal 深层阴影 |
| `CompilePage.tsx` | Notion 主按钮 4px 圆角、参数面板 `--shadow-sm`、成功/失败反馈卡片 |
| `QueryPage.tsx` | 透明背景 textarea、模式选择药丸按钮 9999px、Notion 主按钮 4px 圆角 |
| `QualityPage.tsx` | 分布条形图 4px 圆角、次要按钮 `var(--bg-hover)` 背景 |
| `GraphPage.tsx` | D3 图谱颜色 #0075de / #1aae39 / #1d4ed8、tooltip 4 层阴影 |
| `StatusPage.tsx` | 信息行分隔 `--border-subtle`、卡片 `--shadow-sm`、类型分布条 4px 圆角 |
| `SettingsPage.tsx` | 输入框 `#dddddd` 边框 4px 圆角、主按钮 #0075de、次要按钮 4px 圆角边框 |

## 4. 验证结果

| 检查项 | 结果 |
|--------|------|
| TypeScript 类型检查 | 0 错误 |
| Vite 生产构建 | 成功（CSS 19.35KB gzip 4.71KB, JS 272.84KB gzip 81.56KB） |
| 页面路由 | 8/8 全部返回 HTTP 200 |
| 设计令牌一致性 | 100%（按钮 4px 圆角、输入 #dddddd 边框、药丸 9999px、字重 400/500/600/700） |
| Notion 规范违规 | 0 处（已修复唯一违规：fontWeight 450 → 500） |

## 5. OpenDesign 集成详情

| API | 用途 |
|-----|------|
| `GET /api/design-systems` | 从 151 个系统中筛选 Notion / Mintlify / Clean |
| `GET /api/design-systems/notion` | 获取完整 Notion 设计规范（9 章节） |
| `GET /api/design-systems/mintlify` | 获取阅读优化规范 |
| `GET /api/skills` | 发现 151+ 设计技能 |
| `POST /api/chat` | 通过 Claude agent 分析设计适配方案 |
| `GET /api/agents` | 确认本地 Claude Code agent 可用 |
