# GUI Solver Contract

本文档定义 B8c GUI 与后端求解/审计能力之间的小契约。该契约属于 A/B 共享边界：GUI 通过统一 runner 触发求解、接收事件、读取候选方案池和推荐结果；核心数学算法、评价、审计、下界证明和敏感性分析仍由后端模块负责。

## 目标

- 让 B8c GUI 不直接绑定 A 线 solver 类、脚本输出或 `print()` 进度。
- 统一第 (1)-(3) 问的求解入口，并为第 (4) 问复用候选池做参数敏感性分析留下稳定数据结构。
- 统一 `CandidateSolution -> RoutePlan -> AuditResult` 流程，避免 GUI 自行拼装数学指标。
- 支持后台任务、日志事件和协作式取消。

## 核心术语

- **SolveJob**：一次 GUI 触发的后端任务，包括题目类型、算法标识、参数和可选 `plan_id`。
- **SolveParameters**：GUI 第一版主界面开放的数学参数集合，包含 `T_hour`、`t_hour`、`speed_km_per_hour` 和 `group_count`；`time_limit_hour`、`max_group_upper`、`time_limit_seconds`、`iterations` 等作为后端默认或高级参数保留。
- **AlgorithmRunner**：后端统一求解入口。它接收 `SolveJob`，调用现有 A 线 solver，转换为 `RoutePlan`，再调用 B 线审计，返回 `SolveResult`。
- **SolveEvent**：任务运行过程中的结构化事件，供 GUI 日志、进度条和状态栏展示。
- **SolveCandidate**：候选方案池中的单项，包含 `RoutePlan`、评分、最终审计结果和可比较排序键。
- **SolveResult**：一次任务的完整结果，包含状态、候选池、推荐方案、事件日志和可选错误信息。

## 题目类型

第一版 runner 支持：

- `fixed_groups`：第 (1) 问，固定 `group_count`，默认算法为 `mtsp_local_search`。
- `minimum_groups`：第 (2) 问，默认算法为 `min_groups_search`。
- `unlimited_personnel`：第 (3) 问，默认算法为 `minmax_vrp_search`。

第 (4) 问参数敏感性不单独定义新的 A 线求解算法；B8c 应复用候选方案池并调用 B7 现有参数敏感性入口。

## 边界

- GUI 可以收集参数、选择算法、触发任务、展示日志、取消任务、选择候选、播放动画并导出结果。
- GUI 不直接计算路线指标、审计合法性、上下界证明或敏感性结论。
- runner 不重写 A 线算法，只适配现有 solver 类和 `candidate_to_route_plan` 导出流程。
- 取消为协作式取消：runner 在任务阶段边界检查取消请求；现有 solver 内部尚未支持中断时，不强行终止线程。

## Git 分支规则

对本契约字段、语义或公共 runner 结果结构的修改，必须先走 `shared/...` 分支。B 线 GUI 分支只能消费已经沉淀的共享契约，不夹带破坏 A/B 边界的公共结构变更。
