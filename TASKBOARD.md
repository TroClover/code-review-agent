# BRT Code Review Agent — Task Board v2

## 项目概览

为自动驾驶公司 BRT 部门设计一个 LLM 驱动的代码审查 Agent（3 Agent 架构），解决以下痛点：
- **开发者**：代码质量参差不齐，审查反馈不够具体可操作
- **审查者**：被低级问题淹没，真正需要关注的问题得不到重视
- **整体**：人工审查耗时，成为研发瓶颈

**核心定位**：LLM 审查填补 linter 和人工审查之间的空白——语义级别的代码理解。

**两种使用模式**：
1. **本地 Pre-PR 审查**：开发者提交 PR 前本地运行，提前发现问题
2. **GitHub Bot**：PR 创建时自动触发审查，在 PR 上发 inline comment

---

## 状态说明

| 标记 | 含义 |
|------|------|
| ⬜ | 未开始 |
| 🔄 | 进行中 |
| ✅ | 已完成 |
| 🔍 | 需要人工判断/审查 |
| ❌ | 已删除（伪需求） |

---

## 整体架构（3 Agent + 工具层）

```
PR 触发（webhook / CLI）
  │
  ▼
Orchestrator Agent
  ├── 解析 PR diff
  ├── 构建上下文（含原 Context Agent 逻辑）
  ├── 运行 linter 集成
  └── 决定调用哪些 Agent
  │
  ▼ （并行执行）
  ├──→ Code Review Agent ─┐  各自产出 Issue 列表
  └→ Safety Agent ────────┘
         │
         ▼
Orchestrator Agent（聚合结果：合并 linter → 去重 → 排序 → 过滤）
  │
  ▼
输出：GitHub PR comment / 终端输出 / 报告
```

---

## Task Board

### Phase 0: 项目初始化与架构设计

| # | Task | 描述 | 依赖 | 产出 | 状态 |
|---|------|------|------|------|------|
| 0.1 | 项目结构搭建 | 创建项目骨架、目录结构、依赖管理（pyproject.toml） | 无 | 项目骨架 | ✅ |
| 0.2 | 配置系统设计 | 设计配置：`.breview.yml` 仓库级配置 | 无 | config 模块 | ✅ 需更新 |
| 0.3 | 数据模型定义 | 定义核心数据结构：ReviewRequest, ReviewResult, Issue 等 | 无 | models 模块 | ✅ |
| 0.4 | Agent 通信协议 | 定义 Agent 间消息格式、上下文传递协议 | 0.3 | agent_base 模块 | ✅ |
| 0.5 | Agent 编排框架 | 实现 Orchestrator Agent 的调度逻辑 | 0.4 | orchestrator 模块 | ✅ 需重构 |

### Phase 1: 核心审查引擎

| # | Task | 描述 | 依赖 | 产出 | 状态 |
|---|------|------|------|------|------|
| 1.1 | Diff 解析器 | 解析 git diff，提取变更文件、变更行、变更类型 | 0.1 | diff 模块 | ✅ |
| 1.2 | 代码上下文构建器 | 根据 diff 构建上下文：变更代码 + 周围上下文 + 文件头 + imports | 1.1 | context 模块 | ✅ 合并到 Orchestrator |
| 1.3 | LLM 调用封装 | 统一的 LLM 调用层，支持多模型，含限流、重试、成本追踪 | 0.3 | llm 模块 | ✅ |
| 1.4 | Code Review Agent | 核心审查 Agent：逻辑正确性 + 安全漏洞 + 性能问题 | 0.5, 1.2, 1.3 | code_review_agent 模块 | ✅ |
| 1.5 | 审查结果解析器 | 解析 LLM 输出为结构化 Issue 列表 | 1.4 | parser 模块 | ✅ |
| 1.6 | Safety Agent | 安全关键代码审查：通用安全检查 + 可选自动驾驶领域规则 | 0.5, 1.3 | safety_agent 模块 | ✅ 需更新 |

### Phase 2: Linter 集成与 Profile 系统

| # | Task | 描述 | 依赖 | 产出 | 状态 |
|---|------|------|------|------|------|
| 2.1 | Linter 集成框架 | 支持运行外部 linter（ruff/flake8/clang-tidy），解析输出 | 0.1 | linter 模块 | ⬜ |
| 2.2 | 审查 Profile 系统 | 按仓库/分支配置审查 profile（strict/standard/relaxed） | 0.2 | profile 模块 | ⬜ |
| 2.3 | Profile 配置解析 | 解析 .breview.yml 中的 profile 配置 | 0.2, 2.2 | profile_loader 模块 | ⬜ |
| 2.4 | 结果合并 | 合并 linter 结果和 LLM 审查结果 | 2.1, 1.4, 1.6 | result_merger 模块 | ⬜ |

### Phase 3: 成本控制与质量保障

| # | Task | 描述 | 依赖 | 产出 | 状态 |
|---|------|------|------|------|------|
| 3.1 | Token 预算控制 | 可配置每次审查的 token 预算上限，超限停止审查 | 1.3 | budget 模块 | ⬜ |
| 3.2 | 审查缓存 | 同一文件的相同 diff 不重复审查（基于 diff hash） | 1.1 | cache 模块 | ⬜ |
| 3.3 | 成本监控与报告 | 每次审查的 token 用量和成本实时可见 | 1.3, 3.1 | cost_monitor 模块 | ⬜ |
| 3.4 | 误报处理 | 开发者可标记 issue 为 false positive，后续审查跳过 | 1.5 | false_positive 模块 | ⬜ |
| 3.5 | 优雅降级 | LLM API 不可用时降级到 linter-only 模式 | 1.3, 2.1 | degradation 模块 | ⬜ |

### Phase 4: GitHub 集成

| # | Task | 描述 | 依赖 | 产出 | 状态 |
|---|------|------|------|------|------|
| 4.1 | GitHub App 框架 | 注册 GitHub App，处理 webhook（PR opened/synchronize），认证，限流 | 无 | github 模块 | ✅ |
| 4.2 | PR Review 发布 | 将审查结果发布为 PR inline comments + 总体 summary | 1.5, 4.1 | review_publisher 模块 | ✅ |
| 4.3 | Commit Status 管理 | 设置 GitHub commit status（成功/失败/pending） | 4.1 | status 模块 | ⬜ |
| 4.4 | 增量审查 | PR 更新时仅重新审查变更文件，已解决的 issue 标记为 resolved | 4.2, 3.2 | incremental 模块 | ⬜ |
| 4.5 | 审查结果去重 | 同一问题在 PR 更新时不重复报告 | 4.2 | dedup 模块 | ⬜ |

### Phase 5: 本地 Pre-PR 工具

| # | Task | 描述 | 依赖 | 产出 | 状态 |
|---|------|------|------|------|------|
| 5.1 | CLI 工具开发 | `breview` 命令行工具：本地审查当前分支 vs main 的 diff | 0.5, 1.5 | cli 模块 | ✅ |
| 5.2 | 终端输出美化 | 带颜色、严重等级标注、可操作的修改建议 | 5.1 | cli_formatter 模块 | ✅ |
| 5.3 | Git Hook 集成 | pre-push hook 触发审查（advisory 模式） | 5.1 | hooks 模块 | ✅ |

### Phase 6: 报告与归档

| # | Task | 描述 | 依赖 | 产出 | 状态 |
|---|------|------|------|------|------|
| 6.1 | 报告生成 | 生成结构化审查报告（Markdown），包含统计、详情 | 1.5 | report 模块 | ⬜ |
| 6.2 | 自定义 prompt 片段 | 支持 .breview.yml 中定义团队特定的审查关注点 | 0.2 | custom_prompt 模块 | ⬜ |

### Phase 7: 测试与部署

| # | Task | 描述 | 依赖 | 产出 | 状态 |
|---|------|------|------|------|------|
| 7.1 | 单元测试 | 核心模块的单元测试 | 全部 | tests | 🔄 |
| 7.2 | 集成测试 | 端到端测试：mock GitHub webhook → 全 Agent 流水线 → 发布 comment | 全部 | e2e_tests | ⬜ |
| 7.3 | Agent 协作测试 | 测试多 Agent 并行调度、失败隔离、结果聚合的正确性 | 0.5 | agent_tests | ⬜ |
| 7.4 | 🔍 审查质量评估 | 用历史 PR 评估 agent 审查质量（准确率、召回率） | 全部 | eval 报告 | ⬜ |
| 7.5 | 部署配置 | Docker 化、CI/CD pipeline | 全部 | deploy 配置 | ⬜ |

---

## 推荐执行顺序

```
Phase 0 ──→ Phase 1 ──→ Phase 2 ──→ Phase 3
                                        │
                                        ▼
                                    Phase 4（GitHub）
                                        │
                                        ▼
                                    Phase 5（CLI）
                                        │
                                        ▼
                                    Phase 6（报告）
                                        │
                                        ▼
                                    Phase 7（测试部署）
```

**Phase 2（Linter 集成）和 Phase 3（成本控制）可部分并行。**

---

## 需要人工判断的任务汇总

| 任务 | 需要人工判断的内容 |
|------|-------------------|
| 2.1 Linter 集成 | 确认支持的 linter 列表和默认配置 |
| 7.4 审查质量评估 | 判断评估结果是否达到预期质量标准，决定是否需要调优 |

---

## 关键设计决策

### 3 Agent 协作策略

**并行调度**：Code Review Agent 和 Safety Agent 通过 asyncio 并行执行，共享 Orchestrator 构建的上下文。

**失败隔离**：单个 Agent 超时或报错时，Orchestrator 跳过该 Agent 并在结果中标记，不影响其他 Agent 正常输出。

**降级策略**：LLM API 不可用时，自动降级到 linter-only 模式，确保审查流程不被阻断。

### LLM 策略分层

| Agent | LLM 策略 | 原因 |
|-------|----------|------|
| Code Review Agent | 强模型（GPT-4 / Claude） | 逻辑和安全审查需要深度语义理解 |
| Safety Agent | 强模型 + 领域 prompt | 安全关键代码不能妥协 |
| Orchestrator | 轻量模型 / 规则 | 编排逻辑不需要强推理 |

### 审查 Profile 策略

| Profile | 适用场景 | 检查范围 | 阈值 |
|---------|----------|----------|------|
| strict | main/release 分支 | 全部检查 | 低（1 个 critical 即阻断） |
| standard | feature 分支（默认） | 核心检查 | 中（3 个 critical 阻断） |
| relaxed | 实验性/WIP 分支 | 仅高优先级 | 高（仅安全问题阻断） |
