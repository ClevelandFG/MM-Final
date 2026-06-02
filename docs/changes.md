# 改动说明

本文档用于记录项目每次改动的日期时间、版本号、遇到的问题、对应的解决方案、受改动影响的文件名、具体改动内容等信息。

---

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
