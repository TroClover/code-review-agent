# BRT Code Review Agent — 对话记录

**日期**：2026-05-06
**主题**：设计并实现 BRT 部门企业级代码审查 Agent

---

## 第一轮：需求讨论

**用户**：对于一个做自动驾驶的公司，一个 BRT 部门（better release testing），他们日常会有很多的脚本要写，并且在 GitHub 提交，为了保证代码质量，会耗费大量的人工去审核代码质量。对于实习生，他们的代码数量多，质量又参差不齐；对于正式员工，他们生成的代码每次修改内容涉及到很多过往的内容。设计一个合理的、企业级的 agent。

**Claude**：设计了一个完整的 task-board，包含 7 个 Phase，并提出了关键架构问题。

**用户选择**：
- 部署形式：GitHub + 本地 PR 前的审查
- 审查引擎：LLM 驱动
- 语言栈：Python + C++

---

## 第二轮：需求细化

**用户**：具体都考虑到了哪些需求，将最终需求存储在 markdown 里面。

**Claude**：梳理了 7 大类需求：
1. 用户角色与场景（实习生、正式员工、审查人员、团队 Lead）
2. 审查能力需求
3. 上下文理解需求
4. 集成需求
5. 配置需求
6. 输出需求
7. 非功能需求

**用户确认**：
- 代码审查范围：diff + 全文件审查
- 审查粒度：PR 级别（Claude 建议）
- 输出语言：英文
- 冷启动：用户审查通过的初始编码规范作为 seed

---

## 第三轮：知识系统

**用户**：审查过程可以提炼出 knowledge，用于给编辑代码的人正向反馈。

**用户确认**：
- 知识来源：Agent 审查结果 + 人工 comment（人工权重更高）
- 正反馈触发方式：审查时自动附带
- 知识粒度：粗粒度（团队规范）+ 细粒度（按人/按问题）

---

## 第四轮：需求审查与多 Agent 架构

**用户**：对目前的需求进行检查，指出不合理的要求；对于整个代码审查的 agent，可以使用多 agent 的结构。

**Claude** 发现的问题：
- F-RS-03 审查粒度"只按 PR 级别"过于绝对
- NF-02 "5 分钟内出结果"对大 PR 不现实
- 缺少自动驾驶安全关键代码的特殊处理
- VS Code 扩展不应出现在 v1 范围

**Claude** 提出的改进：
- 新增安全关键代码审查（传感器、仿真环境配置）
- 新增开发者反馈闭环（有用/没用按钮）
- 新增审计日志、限流熔断、数据保留等企业级需求
- SLA 改为分级

**多 Agent 架构**：从 10 个 Agent 精简为 7 个：
1. Orchestrator Agent — 总调度
2. Style Agent — 代码规范
3. Code Review Agent — 逻辑+安全+性能（3 个 sub-prompt）
4. Safety Agent — 安全关键代码
5. Context Agent — 上下文构建
6. Knowledge Agent — 知识提取与关联
7. Report Agent — 报告 + 反馈

**协作流程**：流水线 + 一处并行分叉（Style / Code Review / Safety 并行）

**用户确认**：全部同意。

---

## 第五轮：执行

**用户**：可以开始了，按照 task-board 去执行。

**Claude** 完成了：

Phase 0 — 项目初始化：
- 项目骨架（pyproject.toml、.gitignore、.breview.yml）
- 分层配置系统（config/schema.py + loader.py）
- 数据模型（Issue、ReviewRequest/Result、AgentMessage、KnowledgeEntry）
- Agent 基类和 Orchestrator 编排框架

Phase 1 — 核心审查引擎：
- Diff 解析器
- Context Builder
- LLM 客户端（OpenAI + Anthropic）
- LLM Prompts 模板
- LLM 结果解析器
- Code Review Agent

Phase 2 — 角色与策略：
- 角色识别器
- Style Agent

Phase 3 — 安全审查：
- Safety Agent

Phase 4 — 知识系统：
- 初始编码规范 CODING_STANDARD.md（通过用户审查）
- 知识数据模型
- 知识索引
- Knowledge Agent

Phase 5-9（GitHub 集成、CLI 完善、Dashboard、基础设施、测试部署）未实现，留给后续迭代。

---

## 关键文件清单

| 文件 | 说明 |
|------|------|
| REQUIREMENTS.md | 完整需求文档（中文） |
| TASKBOARD.md | 任务看板（含状态标记） |
| CODING_STANDARD.md | 初始编码规范（Python + C++ + BRT 特定） |
| CHAT_TRANSCRIPT.md | 本对话记录 |
| pyproject.toml | 项目依赖和工具配置 |
| .breview.yml | 示例配置文件 |
| breview/agents/orchestrator.py | Orchestrator Agent（编排核心） |
| breview/agents/style_agent.py | Style Agent（代码规范） |
| breview/agents/code_review_agent.py | Code Review Agent（逻辑+安全+性能） |
| breview/agents/safety_agent.py | Safety Agent（安全关键代码） |
| breview/agents/context_agent.py | Context Agent（上下文构建） |
| breview/agents/knowledge_agent.py | Knowledge Agent（知识提取） |
| breview/agents/report_agent.py | Report Agent（报告生成） |
| breview/llm/client.py | LLM 客户端（多模型支持） |
| breview/llm/prompts.py | Prompt 模板 |
| breview/llm/parser.py | LLM 输出解析器 |
| breview/diff/parser.py | Git diff 解析器 |
| breview/context/builder.py | 上下文构建器 |
| breview/config/schema.py | 配置模型 |
| breview/config/loader.py | 配置加载器 |
| breview/models/*.py | 数据模型 |
| breview/knowledge/index.py | 知识索引 |
| breview/roles/identifier.py | 角色识别器 |
| breview/cli/main.py | CLI 入口 |
| breview/report/generator.py | 报告生成器 |
| tests/test_diff_parser.py | Diff 解析器测试 |
| tests/test_models.py | 数据模型测试 |
| tests/conftest.py | 测试 fixtures |

---

## 待办事项（Phase 5-9）

| Phase | 任务 | 状态 |
|-------|------|------|
| 5 | GitHub App 集成（webhook、PR comment 发布、通知） | 未开始 |
| 6 | 本地 CLI 完善（接入完整 Agent 流水线） | 骨架已有 |
| 7 | Web Dashboard（FastAPI + React） | 未开始 |
| 8 | 基础设施（审计日志、限流熔断、容错、审查豁免） | 骨架已有 |
| 9 | 测试、文档、部署 | 部分测试已有 |
