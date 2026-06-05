# 改动说明

本文档用于记录项目每次改动的日期时间、版本号、遇到的问题、对应的解决方案、受改动影响的文件名、具体改动内容等信息。

---

## 2026-06-05  确认 Python 优先语言策略

- **版本号**：未发布，仍处于第一个可行版本前。
- **问题**：项目语言此前仅列为 Python 或 C++ 候选，尚未形成明确实现策略；A/B 双线并行开发时也缺少明确的 Git 分支与合并规则。
- **解决方案**：
  - 确认项目尽可能只使用 Python，便于图算法、实验调度、可视化、TDD 和 A/B 对接契约落地。
  - 保留后期在明确性能瓶颈或工程必要性出现时引入 C++ 加速核心的可能。
  - 在 `docs/implementation-plan.md` 中明确 C++ 若引入，只能作为内部实现细节，不得绕过路线方案对接契约。
  - 新增 `docs/git-workflow.md`，规定 `main` 稳定主干、A/B 短生命周期功能分支、`shared/...` 契约分支优先合并等协作规则。
  - 在 `AGENTS.md` 和 `docs/implementation-plan.md` 中引用 Git 协作规范，强调共享契约和公共数据结构不得夹带在 A/B 功能分支中。
- **影响文件**：`AGENTS.md`、`docs/implementation-plan.md`、`docs/changes.md`、`docs/git-workflow.md`。

## 2026-06-03  重构双线并行计划与对接契约

- **版本号**：未发布，仍处于第一个可行版本前。
- **问题**：原实施计划按“后端算法/实验展示”拆分，B 线明显依赖 A 线成熟产出，不能保证两人持续并行推进；同时缺少明确的 A/B 对接格式，存在方案字段、单位和节点语义不一致的风险。
- **解决方案**：
  - 将分工重构为 **A 线：路线构造与空间优化线** 和 **B 线：耗时审计、下界证明与参数分析线**。
  - 重写 `docs/implementation-plan.md`，分别给出 A 线与 B 线的阶段计划，并明确第 (1)–(4) 问的主责与协作关系。
  - 新增 `docs/contracts/route-plan-contract.md`，定义 `RoutePlan`、`Route`、`RouteMetrics`、`PlanMetrics`、`AuditResult` 等统一对接结构。
  - 在 `AGENTS.md` 中补充 A/B 对接协议和契约变更规则，强调任何算法输出或审计输入不得绕过契约。
  - 在 `docs/context.md` 中补充“路线方案”术语。
- **影响文件**：`AGENTS.md`、`docs/context.md`、`docs/changes.md`、`docs/implementation-plan.md`、`docs/contracts/route-plan-contract.md`。

## 2026-06-02  工程初始化

- **版本号**：未发布，仍处于第一个可行版本前。
- **问题**：项目仅有任务与理论文档，缺少工程目录、原始数据入口、协作记录目录与分阶段实施计划。
- **解决方案**：
  - 建立工程级目录：`src/`、`tests/`、`data/`、`scripts/`、`apps/`、`experiments/`、`outputs/`、`docs/adr/`、`.agents/`、`.codex/`。
  - 将题面路网表固化为 `data/raw/road_network.tsv`，供后续实现和测试统一读取。
  - 在 `docs/context.md` 中沉淀道路网络、节点类型、巡视路线、路线组、完成时间、均衡性等术语。
  - 更新 `docs/implementation-plan.md`，拆分两条工作量相近的并行推进线，并给出阶段门槛。
  - 润色 `AGENTS.md`，补充范围、语言未定状态、原始数据与 Agent 文件管理约定。
- **影响文件**：`AGENTS.md`、`README.md`、`.gitignore`、`.agents/`、`.codex/`、`apps/`、`data/`、`docs/`、`experiments/`、`outputs/`、`scripts/`、`src/`、`tests/`。
