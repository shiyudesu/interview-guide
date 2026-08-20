# 普通面试参考资料来源

普通文字和语音面试的技术主问题使用 `backend/resources/skills/` 下的 Skill 与 references。
外部题库只参与离线发现和资料维护，生产 API、Worker 和模型调用链不访问这些外部来源。

## 设计目标

- 使用多个题库发现高频问题，避免依赖单一站点的覆盖和表述。
- 使用官方文档核对关键点、版本边界和容易过时的结论。
- 只把经过整理和审核的内容写入运行时 references。
- 保留来源、许可证和用途，避免把“开源代码许可”误认为“线上内容许可”。
- 原始采集结果写入 `.artifacts/`，默认不提交仓库。

## 文件

```text
tools/reference_sources/catalog.json     来源、许可证和允许用途
tools/reference_sources/taxonomy.json    Skill 分类、搜索词和匹配关键词
tools/reference_sources/provenance.json  已维护 reference 的来源记录
tools/scripts/reference_sources.py       校验与离线采集工具
```

GitHub 内容源固定到具体 commit SHA，`trackedBranch` 只用于后续人工检查上游更新，保证同一份
配置重复采集时内容可追溯。

来源用途分为：

- `adapt-with-attribution`：允许整理或改写，发布时仍需满足来源许可证和署名要求。
- `discovery-only`：只用于发现知识点和问题方向，不复制原文或答案。
- `link-only`：只保存最少的题目标题、外部 ID 和链接，不抓取受限正文。
- `verify-only`：官方文档等事实校验来源，不作为批量题目导入源。

遇到无明确许可证、非商业限制、禁止演绎或站点条款不明确的内容时，默认降级为
`discovery-only` 或不使用。许可证判断只是仓库维护规则，不代替正式法律意见。

## 使用方法

校验目录、分类和来源关联：

```bash
python3 tools/scripts/reference_sources.py --root . validate
```

查看来源：

```bash
python3 tools/scripts/reference_sources.py --root . list
```

通过面试鸭的 MCP 搜索上游接口采集 Java 后端候选题：

```bash
python3 tools/scripts/reference_sources.py --root . collect \
  --source mianshiya \
  --skill java-backend \
  --output .artifacts/java-reference-questions.jsonl
```

采集 GitHub Markdown 来源：

```bash
python3 tools/scripts/reference_sources.py --root . collect \
  --source java-guide \
  --source advanced-java \
  --skill java-backend \
  --output .artifacts/java-github-questions.jsonl
```

结构化 GitHub JSON 题库使用相同命令，例如：

```bash
python3 tools/scripts/reference_sources.py --root . collect \
  --source data-engineering-interview-questions \
  --skill data-engineering \
  --output .artifacts/data-engineering-questions.jsonl
```

试运行时可以使用 `--query-limit 2` 限制每个 Skill 的面试鸭查询次数，使用
`--max-per-query` 和 `--max-per-category` 控制输出数量。工具只输出规范化 JSONL，不直接修改
Skill 或 reference 文件。为了避免一次意外下载全部远端来源，`collect` 默认要求至少传一个
`--source`；确需采集全部启用来源时必须显式传入 `--all-enabled`。

## 整理流程

1. 在 `taxonomy.json` 中维护细粒度搜索词，不使用“Java 面试题”之类过宽查询替代分类设计。
2. 采集题目标题、标签、难度、链接和来源信息。
3. 按 Unicode 规范化后的题干去重，再人工处理语义重复和质量问题。
4. 将候选题聚类为知识点，选择少量具有区分度的主问题和追问方向。
5. 使用官方文档核验合格答案关键点、边界条件和当前版本行为。
6. 将原创、精炼后的内容写入 reference，并更新 `provenance.json`。
7. 新建普通面试时，生成服务按题目 `type` 或分类名称匹配 reference，并把受限内容保存为
   `source_context` 快照，供动态追问和最终评估使用。
8. 运行工具测试、后端测试和仓库清单检查。

## 当前扩充范围

- Java 后端：消息队列、分布式与微服务、网络/Linux、安全、工程化和可观测性。
- 前端：工程化、性能、CSS 和前端安全。
- Python 后端：FastAPI、部署与可观测性、PostgreSQL 和 API 安全。
- 系统设计：消息队列、数据库设计和架构安全。
- Go 后端：语言语义、并发、运行时、服务工程、数据存储和生产治理。
- DevOps/SRE：Linux、容器/Kubernetes、可靠性、CI/CD、可观测性、IaC 和平台安全。
- 数据工程：SQL 建模、批处理、流处理、数据仓库、数据质量、编排和平台运维。

## Reference 编写规则

- 单个文件保持聚焦，避免把数百道题直接拼入 Prompt。
- 内容包含覆盖范围、关键判断点、场景追问和常见误区。
- 不复制第三方长篇答案；保留必要署名和链接。
- 涉及安全、数据库一致性、语言版本或框架版本时，必须使用官方资料复核。
- 新增分类时同步更新 `skill.meta.yml`、对应 `SKILL.md`、taxonomy 和 provenance。

生成阶段对多个分类的 reference 采用公平字符预算，确保题目较多时后置分类不会因总长度上限
而完全丢失。
