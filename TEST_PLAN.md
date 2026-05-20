# BRT Code Review Agent — 测试计划

## 测试策略

### 测试层级

| 层级 | 目标 | 工具 | 覆盖范围 |
|------|------|------|----------|
| 单元测试 | 验证单个函数/类的正确性 | pytest | 每个模块的核心函数 |
| 集成测试 | 验证模块间协作 | pytest + mock | Agent 流水线、配置加载 |
| 端到端测试 | 验证完整流程 | pytest + mock GitHub | 从触发到输出 |

### 测试数据

- **测试 diff**：预定义的 git diff 片段，覆盖 Python 和 C++ 代码
- **测试配置**：不同 profile 的 .breview.yml 配置
- **Mock LLM**：模拟 LLM 响应，避免真实 API 调用
- **Mock GitHub**：模拟 GitHub API 响应

---

## 单元测试用例

### TC-1: Diff 解析器（F-CU-01）

| 用例 ID | 描述 | 输入 | 预期输出 |
|---------|------|------|----------|
| TC-1.1 | 解析单文件修改 | 单个文件的 diff | 正确提取文件路径、变更行、变更类型 |
| TC-1.2 | 解析多文件修改 | 多个文件的 diff | 正确解析所有文件 |
| TC-1.3 | 解析新增文件 | 新增文件的 diff | change_type = "added" |
| TC-1.4 | 解析删除文件 | 删除文件的 diff | change_type = "deleted" |
| TC-1.5 | 解析二进制文件 | 二进制文件的 diff | is_binary = True，跳过内容解析 |
| TC-1.6 | 解析空 diff | 空字符串 | 返回空的 ParsedDiff |
| TC-1.7 | 解析大 diff | 包含 1000+ 行变更的 diff | 正确解析，不超时 |

### TC-2: 上下文构建器（F-CU-02, F-CU-04）

| 用例 ID | 描述 | 输入 | 预期输出 |
|---------|------|------|----------|
| TC-2.1 | 构建文件上下文 | 文件变更 + 仓库路径 | 包含 surrounding_code、file_header、function_signatures |
| TC-2.2 | Token 截断 | 超大文件的上下文 | 截断到 token 限制内，优先保留 diff 周围代码 |
| TC-2.3 | 无仓库路径 | 文件变更，无仓库路径 | 返回空上下文，不报错 |

### TC-3: LLM 客户端（NF-02, F-CC-01, F-CC-02）

| 用例 ID | 描述 | 输入 | 预期输出 |
|---------|------|------|----------|
| TC-3.1 | 正常调用 | 有效消息 | 返回 LLMResponse，包含 content、token 用量、成本 |
| TC-3.2 | 成本超限 | 累计成本超过预算 | 抛出 RuntimeError |
| TC-3.3 | 重试机制 | API 调用失败 | 自动重试 3 次，最终失败时抛出异常 |
| TC-3.4 | Token 计数 | 多次调用 | total_tokens 正确累加 |
| TC-3.5 | 成本计算 | 不同模型 | 按模型定价正确计算成本 |

### TC-4: Code Review Agent（F-RC-01~04）

| 用例 ID | 描述 | 输入 | 预期输出 |
|---------|------|------|----------|
| TC-4.1 | 逻辑错误检测 | 包含逻辑错误的 diff | 检测到 issue，severity = critical/major |
| TC-4.2 | 安全漏洞检测 | 包含硬编码密钥的 diff | 检测到 security 类 issue |
| TC-4.3 | 性能问题检测 | 包含低效算法的 diff | 检测到 performance 类 issue |
| TC-4.4 | 跨文件影响 | 修改函数签名的 diff | 检测到对调用方的影响 |
| TC-4.5 | 无问题代码 | 正确的代码 diff | 返回空 issue 列表 |
| TC-4.6 | 二进制文件跳过 | 包含二进制文件的 diff | 跳过二进制文件，不调用 LLM |

### TC-5: Safety Agent（F-RC-02, F-RC-06）

| 用例 ID | 描述 | 输入 | 预期输出 |
|---------|------|------|----------|
| TC-5.1 | 硬编码密钥检测 | 包含 hardcoded password 的 diff | 检测到 critical issue |
| TC-5.2 | SQL 注入检测 | 包含字符串拼接 SQL 的 diff | 检测到 critical issue |
| TC-5.3 | 路径遍历检测 | 包含未验证路径的 diff | 检测到 major issue |
| TC-5.4 | 资源泄漏检测 | 包含未关闭文件句柄的 diff | 检测到 major issue |
| TC-5.5 | 传感器数据验证（领域规则） | 启用领域规则 + 传感器相关代码 | 检测到传感器数据验证问题 |
| TC-5.6 | 仿真配置检查（领域规则） | 启用领域规则 + 仿真配置代码 | 检测到配置参数问题 |
| TC-5.7 | 领域规则禁用 | 未启用领域规则 + 传感器代码 | 不触发领域检查 |
| TC-5.8 | 安全文件过滤 | 非安全相关文件 | 跳过，不调用 LLM |

### TC-6: Orchestrator Agent（F-PR-01~05）

| 用例 ID | 描述 | 输入 | 预期输出 |
|---------|------|------|----------|
| TC-6.1 | strict profile | strict profile + 有 issue 的 diff | 所有 issue 都报告 |
| TC-6.2 | standard profile | standard profile + 有 issue 的 diff | 仅报告 major 以上 |
| TC-6.3 | relaxed profile | relaxed profile + 有 issue 的 diff | 仅报告 critical |
| TC-6.4 | Agent 并行执行 | 需要调用多个 Agent | CodeReview 和 Safety 并行执行 |
| TC-6.5 | Agent 失败隔离 | 一个 Agent 超时 | 其他 Agent 正常完成，结果标记失败 |
| TC-6.6 | 结果去重 | 多个 Agent 报告同一问题 | 合并为一个 issue，保留最高 confidence |
| TC-6.7 | 结果排序 | 多个不同严重等级的 issue | 按 severity 排序（critical > major > minor > info） |

### TC-7: Linter 集成（F-LI-01~03）

| 用例 ID | 描述 | 输入 | 预期输出 |
|---------|------|------|----------|
| TC-7.1 | 运行 ruff | Python 代码 + ruff 配置 | 解析 ruff 输出为 Issue 列表 |
| TC-7.2 | 运行 clang-tidy | C++ 代码 + clang-tidy 配置 | 解析 clang-tidy 输出为 Issue 列表 |
| TC-7.3 | Linter 不可用 | 未安装 linter | 优雅降级，不报错 |
| TC-7.4 | 结果合并 | linter 结果 + LLM 结果 | 合并输出，去重 |

### TC-8: 误报处理（F-FP-01~04）

| 用例 ID | 描述 | 输入 | 预期输出 |
|---------|------|------|----------|
| TC-8.1 | 标记 false positive | 一个 issue + 用户标记 | issue 被标记为 false positive |
| TC-8.2 | 跳过已知误报 | 已标记的 false positive + 相同 issue | 不再报告该 issue |
| TC-8.3 | 误报统计 | 多个 false positive 标记 | 正确统计误报率 |
| TC-8.4 | 配置忽略 | .breview.yml 中配置忽略某类 issue | 该类 issue 不报告 |

### TC-9: 成本控制（F-CC-01~05）

| 用例 ID | 描述 | 输入 | 预期输出 |
|---------|------|------|----------|
| TC-9.1 | Token 用量可见 | 一次审查 | 输出 token 用量和成本 |
| TC-9.2 | 预算超限 | 设置低预算 + 大 diff | 审查在预算耗尽时停止 |
| TC-9.3 | 审查缓存 | 相同 diff 重复审查 | 第二次命中缓存，不调用 LLM |
| TC-9.4 | 缓存失效 | diff 变更 | 缓存失效，重新审查 |
| TC-9.5 | 降级到 linter-only | LLM API 不可用 | 降级到 linter-only 模式 |

### TC-10: 配置系统（CF-01~10）

| 用例 ID | 描述 | 输入 | 预期输出 |
|---------|------|------|----------|
| TC-10.1 | 默认配置 | 无 .breview.yml | 使用默认配置 |
| TC-10.2 | 仓库级配置 | .breview.yml | 覆盖默认配置 |
| TC-10.3 | Profile 配置 | .breview.yml 中定义 profile | 正确加载 profile 配置 |
| TC-10.4 | 忽略模式 | 配置忽略 vendor/** | vendor/ 下的文件不审查 |
| TC-10.5 | 行级豁免 | 代码中有 `# breview: ignore` | 该行不审查 |
| TC-10.6 | 自定义 prompt | .breview.yml 中定义 custom_prompt | prompt 中包含自定义内容 |

### TC-11: 审查结果质量（F-QA-01~03）

| 用例 ID | 描述 | 输入 | 预期输出 |
|---------|------|------|----------|
| TC-11.1 | 可操作建议 | 有 issue 的 diff | 每个 issue 都有 suggestion 字段 |
| TC-11.2 | 结果可复现 | 相同输入两次审查 | 结果一致（低 temperature） |
| TC-11.3 | 自定义 prompt | 配置了 custom_prompt | LLM prompt 中包含自定义内容 |

---

## 集成测试用例

### TC-12: Agent 流水线（端到端）

| 用例 ID | 描述 | 输入 | 预期输出 |
|---------|------|------|----------|
| TC-12.1 | 完整流水线 | PR diff + 配置 + mock LLM | 从触发到输出完整流程 |
| TC-12.2 | CLI 模式 | 本地 diff + CLI 参数 | 终端输出审查结果 |
| TC-12.3 | GitHub 模式 | webhook 事件 + mock GitHub API | PR 上发布 inline comment |
| TC-12.4 | 增量审查 | PR 更新 + 部分文件变更 | 仅重新审查变更文件 |
| TC-12.5 | 大 PR 处理 | 包含 50+ 文件的 PR | 正确拆分审查，不超 token 限制 |

### TC-13: 失败场景

| 用例 ID | 描述 | 输入 | 预期输出 |
|---------|------|------|----------|
| TC-13.1 | LLM API 超时 | 模拟 API 超时 | 重试后降级到 linter-only |
| TC-13.2 | LLM API 限流 | 模拟 429 错误 | 指数退避重试 |
| TC-13.3 | 无效 diff | 格式错误的 diff | 优雅处理，返回错误信息 |
| TC-13.4 | 配置错误 | 格式错误的 .breview.yml | 使用默认配置，输出警告 |

---

## 测试覆盖矩阵

| 需求编号 | 测试用例 |
|----------|----------|
| F-RC-01 | TC-4.1 |
| F-RC-02 | TC-5.1, TC-5.2 |
| F-RC-03 | TC-4.3 |
| F-RC-04 | TC-4.4 |
| F-RC-05 | TC-10.6 |
| F-RC-06 | TC-5.5, TC-5.6, TC-5.7 |
| F-RS-01 | TC-1.1 |
| F-RS-03 | TC-6.4 |
| F-RS-04 | TC-12.5 |
| F-CU-01 | TC-1.1~1.7 |
| F-CU-02 | TC-2.1 |
| F-CU-04 | TC-2.2 |
| F-PR-01~04 | TC-6.1~6.3 |
| F-PR-05 | TC-10.3 |
| F-LI-01~03 | TC-7.1~7.4 |
| F-IG-01 | TC-12.3 |
| F-IG-02 | TC-12.3 |
| F-IG-04 | TC-4.3 |
| F-IG-06 | TC-12.4 |
| F-IG-07 | TC-6.5 |
| F-LO-01 | TC-12.2 |
| F-LO-02 | TC-12.2 |
| F-EX-01 | TC-10.4 |
| F-EX-02 | TC-10.5 |
| F-FP-01~04 | TC-8.1~8.4 |
| F-CC-01~05 | TC-9.1~9.5 |
| F-QA-01 | TC-11.1 |
| F-QA-02 | TC-11.2 |
| F-QA-03 | TC-11.3 |
| NF-02 | TC-9.1, TC-9.2 |
| NF-05 | TC-13.1~13.4 |
| CF-01~10 | TC-10.1~10.6 |
