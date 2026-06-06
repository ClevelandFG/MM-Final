# 文档导航

本文档作为 `docs/` 目录的入口，帮助 A/B 两线快速找到该看的文件。当前先保持现有文件路径稳定，不做大规模搬迁，避免破坏已写入计划、Agent 指令和协作说明中的链接。

## 1. 项目入口

- `task.md`：题面任务原文与问题要求。
- `theories.md`：题面给出的理论背景与建模参考。
- `context.md`：项目术语表，记录已经确认的业务概念。
- `changes.md`：项目变更记录，按时间记录实际修改。

## 2. 契约与共享标准

- `contracts/route-plan-contract.md`：A/B 路线方案对接契约，定义 `RoutePlan`、`Route`、指标字段、节点语义和统一路网实现标准。

## 3. 实施计划

- `implementation-plan.md`：全局分阶段实施计划，说明 A/B 双线职责、共享底基和握手点。
- `detailed-plan-for-track-A.md`：A 线详细开工计划，面向路线构造与空间优化。
- `detailed-plan-for-track-B.md`：B 线详细开工计划，面向耗时审计、下界证明、参数分析与可视化。

## 4. 协作与环境

- `git-workflow.md`：A/B 双线、`shared/...` 分支和主干合并规则。
- `environment-and-dependencies.md`：依赖、可视化/GUI 库和环境策略。
- `setup-python-env.md`：本机 Python 虚拟环境创建与同步说明。

## 5. 整理原则

- 当前文档数量还可以通过导航页管理，暂不迁移文件路径。
- 若后续计划文档、报告文档或实验文档继续增加，再考虑新增 `docs/plans/`、`docs/reports/`、`docs/experiments/` 等子目录。
- 如果迁移文件，必须同步更新 `AGENTS.md`、计划文档、契约文档和 Git 工作流中的引用链接。
