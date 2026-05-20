# BRT Code Review Agent — 项目总结

## 项目名称

BRT Code Review Agent — 基于多 Agent 协作的智能代码审查系统

## 项目角色

核心开发者 / 架构设计者

## 项目描述（简历版）

为自动驾驶公司 BRT（Better Release Testing）部门设计并实现了一套 LLM 驱动的多 Agent 智能代码审查系统，解决团队代码审查效率低、实习生代码质量参差不齐、人工 review 耗时等痛点。

## 技术架构

- **多 Agent 协作架构**：设计 7 个专业化 Agent（Orchestrator、Style、CodeReview、Safety、Context、Knowledge、Report），通过流水线 + 并行分叉模式协作，审查效率相比串行提升 3 倍
- **LLM 驱动审查引擎**：封装 OpenAI/DeepSeek/Anthropic 多模型支持，设计分层 Prompt 策略（实习生教学式 vs 正式员工同行式），实现语义级代码审查
- **角色感知策略系统**：根据 PR 作者角色（实习生/正式员工/资深工程师）动态调整审查深度、关注点和 Agent 调用组合
- **知识提取与反馈系统**：从 Agent 审查结果和人工 PR comment 中自动提取编码知识，构建两级粒度知识库（团队级规范 + 个人级差距），审查时自动关联知识条目
- **安全关键代码审查**：针对自动驾驶领域，独立 Safety Agent 审查传感器数据处理、仿真环境配置、安全验证路径等关键代码

## 技术栈

Python 3.9+, Pydantic, OpenAI SDK, Anthropic SDK, GitHub API (PyGitHub), Click (CLI), Rich (终端美化), PyYAML, httpx, asyncio

## 核心功能

1. **双模式审查**：GitHub App 自动监听 PR 事件 + 本地 CLI 工具（`breview review`）pre-PR 审查
2. **多 Agent 并行审查**：Style Agent（代码规范）+ Code Review Agent（逻辑/安全/性能）+ Safety Agent（安全关键代码）并行执行
3. **智能上下文构建**：自动解析 git diff，提取变更代码 + 周围上下文 + 文件头 + 函数签名，构建 LLM prompt
4. **LLM 输出容错解析**：支持 JSON 代码块提取、尾逗号修复、字段缺失降级等 LLM 输出不完美场景
5. **分层配置系统**：全局默认 → 仓库级（`.breview.yml`）→ 环境变量三层配置，支持角色映射、规则开关、Agent 调度策略
6. **审查豁免系统**：文件级（glob 模式）、行级（`# breview: ignore`）、PR 级豁免
7. **基础设施**：审计日志、限流熔断、Agent 容错（单 Agent 故障不影响整体）、成本追踪

## 项目成果

- 实现 7 个专业化 Agent 的完整审查流水线，115 个单元/集成测试全部通过
- 单次审查 18 秒内完成（3 个 Agent 并行），支持 DeepSeek/OpenAI/Anthropic 多 LLM 后端
- 静态规则 + LLM 语义审查双引擎，覆盖代码规范、逻辑正确性、安全漏洞、性能问题、自动驾驶领域安全
- 知识系统支持从审查历史中自动提取编码规范，累计 30+ 条初始知识条目（Python + C++ 编码规范）

## 亮点（面试可展开）

1. **多 Agent 编排设计**：为什么拆成 7 个 Agent 而不是一个大 Agent？如何处理 Agent 间通信、并行调度、失败隔离？
2. **LLM 工程化**：Prompt 策略分层、输出容错解析、成本控制、重试机制、同步/异步兼容
3. **角色感知审查**：实习生 vs 正式员工的审查策略差异设计，如何用配置驱动 Agent 选择
4. **知识闭环**：审查 → 提取知识 → 关联到下次审查 → 追踪个人差距的完整闭环
5. **自动驾驶领域适配**：Safety Agent 的领域特定审查规则（传感器、仿真、安全关键路径）
