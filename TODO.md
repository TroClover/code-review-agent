# Code Review Agent — 待完成任务

## 已完成 ✅

### 核心功能
- [x] LLM 代码审查（逻辑、安全、性能）
- [x] Linter 集成（ruff/flake8/clang-tidy）
- [x] Profile 系统（strict/standard/relaxed）
- [x] 成本控制（Token 预算、缓存、监控）
- [x] 误报处理（标记和过滤）
- [x] 优雅降级（LLM 不可用时降级到 linter）

### GitHub 集成（P0）
- [x] GitHub Actions 工作流
- [x] PR Comment 发布（ReviewPublisher）
- [x] Commit Status 设置
- [x] CLI `--github` 模式

### 测试
- [x] 69 个单元测试通过
- [x] 端到端测试验证

---

## 待完成

### P1 — 生产级功能

#### 1. 增量审查
- [ ] PR 更新时只审查新变更的文件
- [ ] 已审查的文件跳过（基于 diff hash）
- **状态**: 框架已有（`IncrementalReviewManager`），未集成到主流程

#### 2. 结果去重
- [ ] PR 更新时，已存在的 comment 不重复报告
- [ ] 已解决的 issue 自动标记为 resolved
- **状态**: 框架已有（`deduplicate_issues`），未集成到主流程

#### 3. 审查结果持久化
- [ ] 保存审查历史到本地文件或数据库
- [ ] 支持查看历史审查记录
- **状态**: 未实现

#### 4. 错误处理优化
- [ ] LLM API 限流时自动排队重试
- [ ] GitHub API 限流时优雅降级
- [ ] 网络异常时的重试策略
- **状态**: 基础重试已有，需优化

### P2 — 部署与运维

#### 5. Docker 容器化
- [ ] 编写 Dockerfile
- [ ] docker-compose.yml（用于 webhook 服务器模式）
- **状态**: 未实现

#### 6. Webhook 服务器（可选）
- [ ] FastAPI 服务器接收 GitHub webhook
- [ ] 支持独立部署（不依赖 GitHub Actions）
- **状态**: 框架已有（`WebhookHandler`），未实现服务器

#### 7. 监控与告警
- [ ] 成本超限告警
- [ ] LLM 服务异常告警
- [ ] 审查质量监控
- **状态**: 未实现

### P3 — 文档与优化

#### 8. 文档完善
- [ ] 部署文档（如何配置 GitHub Actions）
- [ ] 用户手册（如何使用 CLI）
- [ ] API 文档（各模块接口说明）
- **状态**: README 已有基础文档

#### 9. 性能优化
- [ ] 大 PR 拆分审查（超过 token 限制时）
- [ ] 并行文件审查优化
- [ ] 审查缓存优化
- **状态**: 基础实现已有

#### 10. 多语言支持扩展
- [ ] 支持更多语言的 linter
- [ ] 语言特定的审查规则
- **状态**: 当前支持 Python + C++

---

## 技术债务

1. **LLM 响应解析**: 偶尔出现 JSON 截断问题，需要更健壮的解析器
2. **测试覆盖**: 缺少 GitHub 集成的端到端测试
3. **配置验证**: 缺少配置文件的 schema 验证
4. **日志系统**: 需要结构化日志和日志级别配置

---

## 下一步建议

1. **立即**: 配置 GitHub Secrets（`BREVIEW_LLM_API_KEY`）
2. **本周**: 完成增量审查和结果去重集成
3. **下周**: 完善部署文档和用户手册
4. **未来**: Docker 容器化和监控告警
