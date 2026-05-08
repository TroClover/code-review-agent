# BRT Code Review Agent — Task Board

## 项目概览

为自动驾驶公司 BRT 部门设计一个企业级代码审查 Agent（多 Agent 架构），解决以下痛点：
- **实习生**：代码量大、质量参差不齐，每个新人都要经历相同的低质量代码阶段
- **正式员工**：修改涉及大量历史上下文，人工 review 成本高
- **整体**：人工审查耗时，成为研发瓶颈

**核心定位**：LLM 驱动的多 Agent 智能代码审查系统，支持两种使用模式：
1. **本地 Pre-PR 审查**：开发者提交 PR 前本地运行，提前发现问题
2. **GitHub Bot**：PR 创建时自动触发审查，在 PR 上发 comment

---

## 状态说明

| 标记 | 含义 |
|------|------|
| ⬜ | 未开始 |
| 🔄 | 进行中 |
| ✅ | 已完成 |
| 🔍 | 需要人工判断/审查 |

---

## 整体架构（7 Agent 协作）

```
PR 触发（webhook / CLI）
  │
  ▼
Orchestrator Agent（编排 Agent）
  ├── 解析 PR diff
  ├── 识别作者角色
  └── 决定本轮需要调用的 Agent 列表
  │
  ▼
Context Agent（上下文 Agent）
  ├── git 历史分析
  ├── 代码索引查询
  └── 跨文件依赖分析
  │
  ▼ （并行执行）
  ├──→ Style Agent（规范 Agent） ──────┐
  ├──→ Code Review Agent（审查 Agent） ┤  各自产出 Issue 列表
  └──→ Safety Agent（安全 Agent） ─────┘
         │
         ▼
Orchestrator Agent（聚合结果：去重 → 排序 → 过滤）
  │
  ▼ （并行）
  ├──→ Knowledge Agent（知识 Agent：提取知识、关联条目）
  └──→ Report Agent（报告 Agent：PR comment + 报告 + 反馈收集）
```

---

## Task Board

### Phase 0: 项目初始化与架构设计

| # | Task | 描述 | 依赖 | 产出 | 状态 |
|---|------|------|------|------|------|
| 0.1 | 项目结构搭建 | 创建项目骨架、目录结构、依赖管理（pyproject.toml）、CI 配置 | 无 | 项目骨架 | ✅ |
| 0.2 | 配置系统设计 | 设计分层配置：全局配置 → 仓库级配置 → 用户级配置（YAML） | 无 | config 模块 | ✅ |
| 0.3 | 数据模型定义 | 定义核心数据结构：ReviewRequest, ReviewResult, Issue, Comment, AgentMessage 等 | 无 | models 模块 | ✅ |
| 0.4 | Agent 通信协议 | 定义 Agent 间消息格式、上下文传递协议、错误处理约定 | 0.3 | agent_base 模块 | ✅ |
| 0.5 | Agent 编排框架 | 实现 Orchestrator Agent 的调度逻辑：角色识别 → Agent 选择 → 并行调度 → 结果聚合 | 0.4 | orchestrator 模块 | ✅ |

### Phase 1: 核心审查引擎

| # | Task | 描述 | 依赖 | 产出 | 状态 |
|---|------|------|------|------|------|
| 1.1 | Diff 解析器 | 解析 git diff，提取变更文件、变更行、变更类型（新增/修改/删除） | 0.1 | diff 模块 | ✅ |
| 1.2 | 代码上下文构建器（Context Agent） | 根据 diff 构建上下文：变更代码 + 周围上下文 + 文件头 + imports | 1.1 | context 模块 | ✅ |
| 1.3 | LLM 调用封装 | 统一的 LLM 调用层，支持多模型（OpenAI/Claude/本地模型），含限流、重试、成本追踪 | 0.3 | llm 模块 | ✅ |
| 1.4 | Code Review Agent | 核心审查 Agent：逻辑正确性 + 安全漏洞 + 性能问题，3 个 sub-prompt 并行执行 | 0.5, 1.2, 1.3 | code_review_agent 模块 | ✅ |
| 1.5 | 审查结果解析器 | 解析 LLM 输出为结构化 Issue 列表（严重等级、位置、建议、说明） | 1.4 | parser 模块 | ✅ |

### Phase 2: 角色与策略系统

| # | Task | 描述 | 依赖 | 产出 | 状态 |
|---|------|------|------|------|------|
| 2.1 | 角色识别模块 | 识别 PR 作者角色（实习生/正式员工/资深工程师），从 GitHub team 或配置映射 | 0.2 | role 模块 | ✅ |
| 2.2 | 角色审查策略 | 不同角色应用不同审查深度和关注点，按角色选择性调用 Agent | 2.1, 0.5 | strategy 模块 | ✅ |
| 2.3 | Style Agent | 代码规范 Agent：命名、格式、import、注释，规则为主 + 轻量 LLM | 0.5, 1.3 | style_agent 模块 | ✅ |
| 2.4 | 自定义规则引擎 | 支持用户自定义审查规则（YAML/Python 插件） | 0.2 | rules 模块 | ⬜ |

### Phase 3: 历史上下文与安全审查

| # | Task | 描述 | 依赖 | 产出 | 状态 |
|---|------|------|------|------|------|
| 3.1 | Git 历史分析器 | 分析文件的变更历史、贡献者、热点区域 | 无 | history 模块 | ⬜ |
| 3.2 | 代码知识索引 | 构建仓库级代码索引（函数签名、类结构、依赖关系） | 无 | index 模块 | ⬜ |
| 3.3 | 上下文窗口管理 | 智能裁剪上下文，确保 LLM 输入不超 token 限制 | 1.2, 3.1 | context_window 模块 | ⬜ |
| 3.4 | Safety Agent | 安全关键代码审查 Agent：传感器数据处理、仿真环境配置、安全验证流程 | 0.5, 1.3, 3.2 | safety_agent 模块 | ✅ |
| 3.5 | 安全关键路径识别器 | 自动标记涉及传感器、控制、安全验证的代码文件和函数 | 3.2 | safety_marker 模块 | ⬜ |

### Phase 4: 知识提取与反馈系统

| # | Task | 描述 | 依赖 | 产出 | 状态 |
|---|------|------|------|------|------|
| 4.1 | 🔍 初始编码规范制定 | 制定 BRT 部门初始编码规范文档（Python + C++），经用户审查后作为知识库 seed | 无 | coding_standard.md | ✅ 已通过审查 |
| 4.2 | 知识数据模型 | 设计知识条目数据结构：类别、严重等级、代码示例（好/坏）、适用场景、来源权重 | 0.3 | knowledge 模块 | ✅ |
| 4.3 | Knowledge Agent — Agent 来源 | 从 agent 审查历史中自动提炼知识模式 | 1.5, 4.2 | knowledge_agent 模块 | ✅ |
| 4.4 | Knowledge Agent — 人工来源 | 从人工 reviewer 的 PR comment 中提取知识，给予更高权重 | 4.2 | human_comment_extractor 模块 | ⬜ |
| 4.5 | 知识索引与检索 | 构建知识库索引，两级粒度：团队级规范 + 个人/问题级条目 | 4.2 | knowledge_index 模块 | ✅ |
| 4.6 | 审查时知识附带 | 在审查输出中自动关联相关知识条目，附加到 review comment 中 | 4.5, 1.5 | knowledge_attacher 模块 | ⬜ |
| 4.7 | 个人知识差距追踪 | 追踪每个开发者反复违反的知识条目，生成个人薄弱点画像 | 4.5 | gap_tracker 模块 | ⬜ |
| 4.8 | 🔍 新人 onboarding 清单 | 基于实习生初始代码提交，自动生成个性化学习清单 | 4.7 | onboarding 模块 | ⬜ |
| 4.9 | 开发者反馈闭环 | review comment 附带"有用/没用"反馈按钮，反馈数据用于优化 prompt 和知识权重 | 4.6 | feedback 模块 | ⬜ |

### Phase 5: GitHub 集成与通知

| # | Task | 描述 | 依赖 | 产出 | 状态 |
|---|------|------|------|------|------|
| 5.1 | GitHub App 框架 | 注册 GitHub App，处理 webhook（PR opened/synchronize），认证，限流 | 无 | github 模块 | ✅ |
| 5.2 | PR Review 发布 | 将审查结果发布为 PR review comments（行级 comment + 总体 summary + 反馈按钮） | 1.5, 5.1 | review_publisher 模块 | ✅ |
| 5.3 | Review 状态管理 | 处理 re-review、增量审查、review dismiss | 5.2 | state 模块 | ✅ |
| 5.4 | 通知集成 | 审查完成后通过 Slack / 邮件 / 飞书通知相关人员 | 5.2 | notification 模块 | ✅ |

### Phase 6: 本地 Pre-PR 工具

| # | Task | 描述 | 依赖 | 产出 | 状态 |
|---|------|------|------|------|------|
| 6.1 | CLI 工具开发 | `breview` 命令行工具：本地审查当前分支 vs main 的 diff，调用完整 Agent 流水线 | 0.5, 1.5 | cli 模块 | ✅ |
| 6.2 | 终端输出美化 | 带颜色、严重等级标注、知识链接、可操作的修改建议 | 6.1 | cli_formatter 模块 | ✅ |
| 6.3 | Git Hook 集成 | pre-push hook 自动触发审查，可配置是否阻断 push | 6.1 | hooks 模块 | ✅ |

### Phase 7: 报告与 Dashboard

| # | Task | 描述 | 依赖 | 产出 | 状态 |
|---|------|------|------|------|------|
| 7.1 | Report Agent — 报告生成 | 生成结构化审查报告（Markdown/HTML），包含统计、趋势、详情 | 1.5 | report_agent 模块 | ⬜ |
| 7.2 | Web Dashboard | FastAPI 后端 + React 前端：查看审查历史、统计、配置规则 | 7.1, 5.1 | dashboard | ⬜ |
| 7.3 | 数据统计与洞察 | 按人员/项目/时间段统计审查数据，发现高频问题模式 | 7.2 | analytics 模块 | ⬜ |

### Phase 8: 基础设施与可靠性

| # | Task | 描述 | 依赖 | 产出 | 状态 |
|---|------|------|------|------|------|
| 8.1 | 审计日志系统 | 所有审查操作可追溯：谁触发、审查了什么、结果如何 | 0.3 | audit 模块 | ⬜ |
| 8.2 | 限流与熔断 | GitHub API 和 LLM API 调用限流，超限时优雅降级 | 1.3, 5.1 | ratelimit 模块 | ⬜ |
| 8.3 | Agent 容错机制 | 单个 Agent 失败不影响其他 Agent，超时跳过并标记 | 0.5 | fault_tolerance 模块 | ⬜ |
| 8.4 | 审查豁免系统 | 文件级豁免（自动生成代码）+ 行级豁免（`# breview: ignore`）+ PR 级豁免 | 0.2 | exemption 模块 | ⬜ |

### Phase 9: 测试、文档与部署

| # | Task | 描述 | 依赖 | 产出 | 状态 |
|---|------|------|------|------|------|
| 9.1 | 单元测试 | 核心模块的单元测试 | 全部 | tests | ⬜ |
| 9.2 | 集成测试 | 端到端测试：mock GitHub webhook → 全 Agent 流水线 → 发布 comment | 全部 | e2e_tests | ⬜ |
| 9.3 | Agent 协作测试 | 测试多 Agent 并行调度、失败隔离、结果聚合的正确性 | 0.5 | agent_tests | ⬜ |
| 9.4 | 🔍 审查质量评估 | 用历史 PR 评估 agent 审查质量（准确率、召回率），需人工判断评估结果 | 全部 | eval 报告 | ⬜ |
| 9.5 | 部署配置 | Docker 化、K8s 部署配置、CI/CD pipeline | 全部 | deploy 配置 | ⬜ |
| 9.6 | 用户文档 | 使用指南、配置说明、API 文档 | 全部 | docs | ⬜ |

---

## 推荐执行顺序

```
Phase 0 ──→ Phase 1 ──→ Phase 2 ──→ Phase 3
                                        │
                                        ▼
                              Phase 4（知识系统）
                                        │
                        ┌───────────────┼───────────────┐
                        ▼               ▼               ▼
                    Phase 5         Phase 6         Phase 7
                   (GitHub)        (本地CLI)       (报告Dashboard)
                        │               │               │
                        └───────────────┼───────────────┘
                                        ▼
                                    Phase 8（基础设施）
                                        │
                                        ▼
                                    Phase 9（测试部署）
```

**Phase 4.1（初始编码规范）可与 Phase 0 并行启动。Phase 5/6/7 可部分并行。**

---

## 需要人工判断的任务汇总

| 任务 | 需要人工判断的内容 |
|------|-------------------|
| 4.1 初始编码规范 | 审查编码规范内容，确认规则合理性、覆盖面、严重等级划分 |
| 4.8 新人 onboarding 清单 | 确认自动生成的学习清单内容是否合理、是否有遗漏 |
| 9.4 审查质量评估 | 判断评估结果是否达到预期质量标准，决定是否需要调优 |

---

## 关键设计决策

### 多 Agent 协作策略

**并行调度**：Style / Code Review / Safety 三个审查 Agent 通过 asyncio 并行执行，共享 Context Agent 的输出。Orchestrator 负责聚合结果：去重（同一问题多个 Agent 重复报告）→ 排序（严重等级 + 相关性）→ 过滤（按角色阈值）。

**按角色选择性调用**：实习生触发全部 Agent；正式员工可跳过 Style Agent；资深员工只触发 Safety Agent + Code Review Agent 的核心 sub-prompt。

**失败隔离**：单个 Agent 超时或报错时，Orchestrator 跳过该 Agent 并在结果中标记，不影响其他 Agent 正常输出。

### LLM 策略分层

| Agent | LLM 策略 | 原因 |
|-------|----------|------|
| Style Agent | 轻量模型 / 规则引擎 | 规范检查不需要强推理能力，成本优先 |
| Code Review Agent | 强模型（GPT-4 / Claude） | 逻辑和安全审查需要深度语义理解 |
| Safety Agent | 强模型 + 领域 prompt | 安全关键代码不能妥协，需要最强推理 |
| Knowledge Agent | 轻量模型 | 知识提取是模式匹配，不需要强推理 |
| Orchestrator / Context / Report | 无需 LLM | 纯逻辑和工具调用 |

### 分层审查流程

```
PR 提交/本地触发
    │
    ▼
[Orchestrator] 解析 diff → 识别角色 → 选择 Agent
    │
    ▼
[Context Agent] 构建上下文（历史 + 索引 + 依赖）
    │
    ▼
[并行] Style Agent + Code Review Agent + Safety Agent
    │
    ▼
[Orchestrator] 聚合：去重 → 排序 → 过滤
    │
    ▼
[并行] Knowledge Agent（知识关联） + Report Agent（输出）
    │
    ▼
[输出] GitHub PR comment（带反馈按钮） / 终端输出 / Dashboard
```
