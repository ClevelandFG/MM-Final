# 改动说明

本文档用于记录项目每次改动的日期时间、版本号、遇到的问题、对应的解决方案、受改动影响的文件名、具体改动内容等信息。

---

## 2026-06-10  沉淀并实现 B4 下界分析

- **版本号**：未发布，仍处于第一个可行版本前。
- **问题**：B4 即将进入组数下界与不可能性分析阶段，需要明确哪些下界第一版要做、哪些证明或候选方案对比留到后续阶段；同时必须避免“B4 现在不做”的内容在 B5/B6 中丢失，并将已拍板口径落到可测试代码中。
- **解决方案**：
  - 在 `docs/detailed-plan-for-track-B.md` 的 B4 阶段新增 22 条已拍板决策，确认 B4 走 `b/lower-bound-analysis`，模块为 `mm_final.evaluation.lower_bounds`，输出 `LowerBoundReport` 和 Markdown 摘要。
  - 确认 B4 第一版只做总停留时间容量下界、单点往返下界和简单集合负载下界；不做复杂整数规划证明，不读取 A 线候选方案池，不直接输出最少组数或第 (3) 问最终结论。
  - 明确不可能性状态使用 `lower_bound_impossible`、`not_excluded`、`insufficient_evidence`，并要求每个下界条目标注 `strict/provable`、`screening_only` 或 `heuristic`。
  - 新增 `mm_final.evaluation.lower_bounds`，实现 `LowerBoundParameters`、`LowerBoundEntry`、`GroupLowerBound`、`LowerBoundReport`、`compute_lower_bound_report()`、`default_k_values()` 和 `lower_bound_report_to_markdown()`。
  - `GroupLowerBound.status` 只由 `strict/provable` 证据决定；距离分层集合当前作为 `screening_only` 说明项进入 Markdown，不参与强排除。
  - 新增 B4 单测，覆盖小图手算、严格下界排除、`to_dict()`、Markdown 摘要和正式路网 smoke。
  - 在 B5 阶段补充继承事项：读取 B4 下界报告、组合 A 线候选方案池和 B3 final 审计、计算上下界差距，并禁止把筛查性弱下界当作强排除依据。
  - 在 B6 阶段补充继承事项：使用 B4 无限人手完成时间下界，结合候选路线形成上下界差距；只有上下界合拢时才宣称强最优结论。
  - 在 `docs/context.md` 补充下界、强排除和上下界差距术语。
- **影响文件**：`src/mm_final/evaluation/lower_bounds.py`、`src/mm_final/evaluation/__init__.py`、`tests/test_lower_bounds.py`、`docs/detailed-plan-for-track-B.md`、`docs/implementation-plan.md`、`docs/context.md`、`docs/changes.md`。

## 2026-06-09  实现 B3 可行性审计器

- **版本号**：未发布，仍处于第一个可行版本前。
- **问题**：B2 已能复算指标并输出诊断，但仍缺少 B3 的最终合法性判定层；A 线候选方案需要能被 B 线按 `candidate` 或 `final` 口径审计，并得到可用于修复沟通的错误、警告和 Markdown 摘要。
- **解决方案**：
  - 新增 `mm_final.evaluation.route_plan_auditor`，提供 `audit_route_plan()`、`audit_validation_result()`、`audit_route_plan_json()` 和 `audit_result_to_markdown()`。
  - `audit_route_plan()` 复用 B2 `evaluate_route_plan()`，不重新实现距离或耗时计算，并将 schema、覆盖、路径和指标诊断分类到 `AuditResult.schema_valid`、`coverage_valid`、`route_valid` 和 `metric_valid`。
  - 实现 `candidate` 与 `final` 两种审计模式：`candidate` 保留 schema 和展开路径坏边为硬错误，将覆盖遗漏、重复、空路线和 metrics 不一致降级为 warning；`final` 将这些问题作为正式审计失败原因。
  - 实现文件级 helper，使无法解析的 JSON 或 `ValidationResult` 也能返回 `schema_valid = false` 的 `AuditResult`。
  - 实现 Markdown 审计摘要，标注审计模式、四类有效性字段、复算指标、错误和警告，用于人工分析和报告草稿。
  - 新增 `tests/test_route_plan_auditor.py`，覆盖合法 final 审计、final 错误分类、candidate 降级、schema helper、JSON helper 和 Markdown 摘要。
  - 在 B 线详细计划和实施计划中记录 B3 已落地能力。
- **影响文件**：`src/mm_final/evaluation/route_plan_auditor.py`、`src/mm_final/evaluation/__init__.py`、`tests/test_route_plan_auditor.py`、`docs/detailed-plan-for-track-B.md`、`docs/implementation-plan.md`、`docs/changes.md`。

## 2026-06-09  确认 B3 审计模式与 Markdown 摘要决策

- **版本号**：未发布，仍处于第一个可行版本前。
- **问题**：B3 已确认需要 `candidate` 和 `final` 两种审计模式，但无法解析的方案如何进入审计、候选模式如何降级、是否修改 `AuditResult` 增加机器可读模式字段、是否同步生成 Markdown 摘要仍需拍板。
- **解决方案**：
  - 确认核心 `audit_route_plan()` 只接收已解析的 `RoutePlan`；无法解析的 JSON 或 `ValidationResult` 由 helper 返回 `schema_valid = false` 的 `AuditResult`。
  - 确认 `candidate` 模式中 schema 错误和展开路径坏边仍为 error，覆盖遗漏、重复、空路线和 metrics 不一致降级为 warning。
  - 确认第一版不修改 `AuditResult` 新增机器可读 `mode` 字段，只在 warning、error 或 Markdown 摘要中标注审计模式；若后续 GUI、报告生成器或批量审计仪表盘需要自动区分 `candidate` 与 `final`，再走 `shared/...` 评估契约变更。
  - 确认 B3 同步生成 Markdown 审计摘要，作为结构化 `AuditResult` 的人工分析和报告草稿视图，不替代结构化结果。
  - 在 `docs/context.md` 中补充审计模式术语。
- **影响文件**：`docs/detailed-plan-for-track-B.md`、`docs/implementation-plan.md`、`docs/context.md`、`docs/changes.md`。

## 2026-06-09  沉淀 B3 可行性审计器决策并同步 B 线编号

- **版本号**：未发布，仍处于第一个可行版本前。
- **问题**：`docs/implementation-plan.md` 中 B 线阶段编号仍沿用旧口径，将 B3 写成“组数下界与不可能性分析”，与 `docs/detailed-plan-for-track-B.md` 中已经细化的 B0-B8 编号不一致；同时 B3 可行性审计器的分支、模块、入口、审计模式和严格性规则需要沉淀，避免后续实现时和 B2 评价器或 B4 下界分析混在一起。
- **解决方案**：
  - 将 `docs/implementation-plan.md` 的 B 线阶段同步为 B0 契约落地、B1 路网语义、B2 方案评价器、B3 可行性审计器、B4 组数下界、B5 24 小时最少组数、B6 人员足够时最短完成时间、B7 参数敏感性分析、B8 GUI 与可视化交付。
  - 修正 A/B 握手点中对 B 线阶段的旧引用，尤其是任意组数方案池对接由旧 `B4` 改为当前 `B5`。
  - 在 `docs/detailed-plan-for-track-B.md` 的 B3 阶段新增已拍板决策，确认 B3 本体走 `b/route-plan-auditor`，模块为 `mm_final.evaluation.route_plan_auditor`，核心入口为 `audit_route_plan(...) -> AuditResult`。
  - 确认 B3 复用 B2 `evaluate_route_plan()`，作为 B0/B2 之上的合法性终审层；B3 不做下界、不实现 A 线算法、不修改 `AuditResult` 契约字段。
  - 确认 B3 第一版支持 `candidate` 与 `final` 两种模式；`final` 是严格终审，`candidate` 用于 A 线中间候选方案诊断，具体降级清单留作后续第 16 题继续拍板。
  - 在 `docs/context.md` 中补充可行性审计、候选审计和最终审计三个术语。
- **影响文件**：`docs/implementation-plan.md`、`docs/detailed-plan-for-track-B.md`、`docs/context.md`、`docs/changes.md`。

## 2026-06-07  实现 B2 共享评分底座

- **版本号**：未发布，仍处于第一个可行版本前。
- **问题**：B2 需要先补齐 A/B 两线共同使用的快速评分核心，使 A 线后续能自然接入 `Clarke-Wright savings`、`k-medoids / cluster-first route-second`、`2-opt`、`relocate` 和模拟退火，同时避免 B 线评价器变成 A 线每一步优化的阻塞点。
- **解决方案**：
  - 在 `RoadNetwork` 上新增 `shortest_path()` 公共接口，返回 `ShortestPath(distance_km, node_path)`。
  - 新增 `mm_final.routing` 中性包，提供 `CandidateSolution`、`CandidateRoute`、`DistanceMatrix`、`RoutePath`、`ObjectiveSpec`、`Score`、`ScoreDiagnostic`、`SolutionPool` 等共享结构。
  - 实现候选解评分，覆盖路线距离、总距离、最大/最小路线距离、距离极差、总耗时、最大/最小路线耗时、耗时极差、空路线 penalty、固定组数 mismatch penalty、缺失/重复必访点 penalty 和轻量诊断。
  - 实现基础 move primitive：路线片段反转、跨路线单节点迁移和节点交换；这些操作只生成新候选，不枚举邻域或执行搜索策略。
  - 实现 `CandidateSolution -> RoutePlan` 导出器，默认保留 `expanded_node_path`、`distance_km` 和 `metrics` 为 `null`，也支持在提供距离矩阵时补全最短路展开路径和距离。
  - 实现方案池 `SolutionPool`，按 `Score.sort_key` 保留 top-n 候选和当前最优。
  - 新增 `tests/test_routing_core.py`，覆盖最短路、距离闭包、候选解评分、固定组数惩罚、分组组合、move primitive、导出器和方案池。
- **影响文件**：`src/mm_final/network/road_network.py`、`src/mm_final/network/__init__.py`、`src/mm_final/routing/`、`src/mm_final/__init__.py`、`tests/test_routing_core.py`、`docs/changes.md`。

## 2026-06-07  实现 B2 路线方案评价器

- **版本号**：未发布，仍处于第一个可行版本前。
- **问题**：B 线需要一个权威评价与报告复核入口，能对手工或 A 线输出的 `RoutePlan` 复算距离、停留时间、行驶时间、完成时间、瓶颈路线和均衡摘要，同时保留 warning/error 诊断但不提前替代 B3 审计器。
- **解决方案**：
  - 新增 `mm_final.evaluation.route_plan_evaluator`，提供 `EvaluationParameters`、`EvaluationResult`、`CoverageSummary`、`DistanceBalanceSummary` 和 `evaluate_route_plan()`。
  - 评价器显式接收 `RoutePlan + RoadNetwork + EvaluationParameters`，若未传参数则从 `RoutePlan.parameters` 读取题面参数默认值。
  - 复算每条路线的 `RouteMetrics` 和全方案 `PlanMetrics`，并在 `EvaluationResult` 中返回 `route_metrics_by_id`、`plan_metrics`、`expanded_paths_by_route_id`、`coverage_summary`、`bottleneck_route_ids`、`distance_balance` 和 `time_breakdown_by_route_id`。
  - 对输入 `distance_km`、`Route.metrics`、`Plan.metrics` 逐字段复核，不一致时给 warning 并使用复算值；nullable metrics 为 `null` 时正常复算，不给 warning。
  - 对空路线、遗漏必访点、重复必访点、展开路径与最短路展开不一致、展开路径相邻节点无边等情况输出结构化 diagnostic；其中展开路径无边使用 error 级 diagnostic，但仍按最短路口径复算指标。
  - 提供 `EvaluationResult.to_dict()`，便于后续 GUI、报告和实验记录序列化。
  - 新增 `tests/test_route_plan_evaluator.py`，覆盖小图复算、metrics 差异 warning、空路线 warning、覆盖摘要、展开路径差异、坏边诊断、瓶颈路线、距离均衡摘要、JSON 序列化和官方 B0 JSON 夹具 smoke。
- **影响文件**：`src/mm_final/evaluation/`、`src/mm_final/__init__.py`、`tests/test_route_plan_evaluator.py`、`docs/changes.md`。

## 2026-06-06  沉淀 B2 方案评价器决策与均衡性口径

- **版本号**：未发布，仍处于第一个可行版本前。
- **问题**：B2 方案评价器即将实现，需要明确最短路公共接口、评价器边界、参数来源、距离与停留时间口径、诊断策略、输出结构、测试夹具和模块位置；同时“均衡性”在题面中表述较模糊，需要给出项目内的明确解释。
- **解决方案**：
  - 在 `docs/detailed-plan-for-track-B.md` 的 B2 阶段补充 28 条已拍板决策，确认最短路公共接口先走 `shared/shortest-path-core`，评价器本体走 `b/...` 分支。
  - 在 B2 目标下新增评价拆分原则，明确共享快速评分核心服务 A 线高频优化，B 线权威评价与报告复核服务阶段性候选方案和最终结果。
  - 在 B2 规划中补充 A 线优化接入所需的最小共享改进并集，包括最短路闭包、`CandidateSolution`、`ObjectiveSpec`、路线评分、邻域操作、导出器和方案池。
  - 沉淀 B2 扩展决策，包括共享评分底座分支、`mm_final.routing` 中性包、三层评价拆分、`CandidateSolution`、`DistanceMatrix`、`Score`、空路线 penalty/warning、分组器输出节点组、move primitive、方案池、导出器和完成边界。
  - 明确 B2 不实现五种经典算法主体，只提供 `Clarke-Wright savings`、`k-medoids`、`2-opt`、`relocate` 和模拟退火所需的稳定接口与基础操作；算法主体留给 A 线。
  - 沉淀 B2 b 段权威评价与报告复核决策，包括 `b/route-plan-evaluator` 分支、`mm_final.evaluation.route_plan_evaluator` 模块、`evaluate_route_plan()` 入口、`EvaluationParameters`、`EvaluationResult`、结构化 diagnostic、指标逐字段复核、覆盖摘要、瓶颈路线、距离均衡摘要、序列化辅助和测试夹具范围。
  - 在 `docs/detailed-plan-for-track-A.md` 与 `docs/implementation-plan.md` 中为 A 线推荐五种优先实现的经典算法：`Clarke-Wright savings`、`k-medoids / cluster-first route-second`、`2-opt`、`relocate` 和模拟退火。
  - 明确 B2 负责复算与诊断，不提前承担 B3 的合法性终审；输出 `route_metrics_by_id`、`plan_metrics` 和 `diagnostics`。
  - 在 `docs/context.md` 中补充均衡性的术语解释，区分路线距离、总耗时、服务节点数等不同工作负载口径。
  - 在 `docs/implementation-plan.md` 中补充第 (1) 问初期按路线距离均衡理解，第 (2)–(4) 问按耗时和瓶颈路线理解。
- **影响文件**：`docs/detailed-plan-for-track-A.md`、`docs/detailed-plan-for-track-B.md`、`docs/context.md`、`docs/implementation-plan.md`、`docs/changes.md`。

## 2026-06-06  补充文档导航与路线契约中的统一路网标准

- **版本号**：未发布，仍处于第一个可行版本前。
- **问题**：`docs/` 根目录中的 Markdown 文件逐渐增多，查找入口不够清晰；同时统一路网标准已写入计划和 Agent 指令，但路线方案对接契约中尚未明确要求实现层复用 `mm_final.network`。
- **解决方案**：
  - 新增 `docs/README.md` 作为文档导航，按项目入口、契约与共享标准、实施计划、协作与环境分组说明现有文档。
  - 在 `docs/contracts/route-plan-contract.md` 中新增统一路网实现标准，明确 A/B 两线必须基于 `mm_final.network` 解释节点、读取路网和复算路线。
  - 暂不迁移现有文档路径，避免破坏已经写入计划、Agent 指令和协作说明的引用链接。
- **影响文件**：`docs/README.md`、`docs/contracts/route-plan-contract.md`、`docs/changes.md`。

## 2026-06-06  确认 A/B 统一路网标准并新增 A 线计划

- **版本号**：未发布，仍处于第一个可行版本前。
- **问题**：A 线可能稍晚开工，不能依赖人工等待确认；B1 已经落地的公共路网底基需要直接成为 A/B 两线统一标准，并在 A 线可见文档中明确提醒。
- **解决方案**：
  - 在 `AGENTS.md` 中明确 `shared/road-network-core` 中的路网读取、节点分类、边权校验、连通性校验和 `mm_final.network` 是 A/B 两线最终统一标准。
  - 在 `docs/implementation-plan.md` 中新增统一路网标准说明，并更新 A1 阶段要求，要求 A 线复用 `mm_final.network`。
  - 新增 `docs/detailed-plan-for-track-A.md`，提醒 A 线开工前确认共享路网标准、路线方案契约和 Git 分支规则，并建议先细化自己的执行计划。
- **影响文件**：`AGENTS.md`、`docs/implementation-plan.md`、`docs/detailed-plan-for-track-A.md`、`docs/changes.md`。

## 2026-06-06  实现 B1 公共路网底基

- **版本号**：未发布，仍处于第一个可行版本前。
- **问题**：A/B 两线都需要统一的路网读取、节点分类、边权校验和连通性校验；同时项目协作复杂，需要智能体在关键操作前后主动提示 Git 分支、提交和推送策略。
- **解决方案**：
  - 在 `AGENTS.md` 中新增 Git 操作建议约束，要求智能体在关键操作前后说明应在哪个分支修改、是否同步 `main`、是否提交、是否推送、是否走 `shared/...` 分支。
  - 新增 `mm_final.network` 包，提供 `NodeType`、节点常量、`classify_node`、`RoadNetwork`、正式 TSV 默认读取、自定义 TSV 读取和结构化路网诊断。
  - 将 B0 契约模块中的节点常量迁移到 `mm_final.network.nodes`，由契约模块导入复用，避免节点语义重复维护。
  - 将 `networkx` 加入主依赖，并更新 `uv.lock`。
  - 新增 `tests/fixtures/road_networks/` 非法 TSV 夹具和 `tests/test_road_network.py`，覆盖节点分类、正式 TSV 节点/边数、必访节点覆盖、只读副本、表头错误、未知节点、非正边权、重复无向边和不连通分量诊断。
- **影响文件**：`AGENTS.md`、`pyproject.toml`、`uv.lock`、`src/mm_final/network/`、`src/mm_final/contracts/route_plan.py`、`tests/fixtures/road_networks/`、`tests/test_road_network.py`、`docs/environment-and-dependencies.md`、`docs/changes.md`。

## 2026-06-06  沉淀 B1 公共路网底基决策

- **版本号**：未发布，仍处于第一个可行版本前。
- **问题**：B1 即将实现路网语义与节点分类复核，需要先明确哪些内容属于 A/B 共享底基，以及节点语义、TSV 读取、图结构、依赖、校验诊断和测试边界，避免 A/B 两线重复实现路网基础。
- **解决方案**：
  - 在 `docs/detailed-plan-for-track-B.md` 的 B1 阶段补充 26 条已拍板决策。
  - 确认 B1 公共底基在 `shared/road-network-core` 分支实现，代码放在 `mm_final.network`，节点常量迁到 `mm_final.network.nodes`。
  - 确认使用 `NodeType` 枚举、自定义 `RoadNetwork` 包装 NetworkX、无向加权图、严格 TSV 校验、结构化诊断、非法 TSV 夹具和正式 TSV 节点/边数断言。
  - 明确 B1 不实现最短路、路线评价器或 B2 内容，最短路能力留到后续 B2/A1 握手或新的共享分支。
- **影响文件**：`docs/detailed-plan-for-track-B.md`、`docs/changes.md`。

## 2026-06-06  沉淀 B0 契约落地决策

- **版本号**：未发布，仍处于第一个可行版本前。
- **问题**：B 线准备进入 B0 契约落地阶段，需要明确公共模型分支、数据模型形态、夹具格式、必访顺序语义、错误等级、nullable 字段口径和测试框架，避免 A/B 两线对 `RoutePlan` 的理解漂移。
- **解决方案**：
  - 在 `docs/contracts/route-plan-contract.md` 中补充 `required_visit_order` 与 `expanded_node_path` 的区别，明确 `O` 和辅助道路节点不得出现在必访顺序中。
  - 明确 nullable 字段必须保留字段名，暂未计算时写为 `null`，不得省略字段。
  - 在 `docs/detailed-plan-for-track-B.md` 的 B0 阶段补充已拍板决策清单，包括 shared 分支、dataclass、JSON 夹具、`tests/fixtures/route_plans/`、两类 smoke 样例、错误等级、额外字段 warning、内部结构化诊断、精确 schema 版本、B0 不复算指标、非法夹具范围和 pytest。
  - 明确 `O` 虽然是大写字母节点，但语义上是县政府所在地，不属于乡镇必访节点。
- **影响文件**：`docs/context.md`、`docs/contracts/route-plan-contract.md`、`docs/detailed-plan-for-track-B.md`、`docs/changes.md`。

## 2026-06-06  实现 B0 契约模型与夹具测试

- **版本号**：未发布，仍处于第一个可行版本前。
- **问题**：B0 需要将路线方案契约落地为可运行的数据模型、JSON 夹具和读取校验测试，作为后续评价器、审计器和 A/B 对接的共同入口。
- **解决方案**：
  - 新增 `pyproject.toml` 和 `uv.lock`，建立 pytest 开发依赖和 `src` 测试路径。
  - 新增 `src/mm_final/contracts/route_plan.py`，使用标准库 `dataclass` 实现 `RoutePlan`、`Route`、`RouteMetrics`、`PlanMetrics`、`AuditResult` 和 B0 读取校验。
  - 新增 `tests/fixtures/route_plans/` 下的 schema smoke、full coverage smoke、非法方案和额外字段 warning 夹具。
  - 新增 `tests/test_route_plan_contract.py`，覆盖 schema 读取、完整覆盖、缺 nullable 字段、错误 schema 版本、`O`/辅助节点误入必访顺序、额外字段 warning 等 B0 决策。
  - 更新环境说明，记录当前 `pyproject.toml` 已建立，`requires-python >=3.9` 是兼容 A 线现有环境的临时下界。
- **影响文件**：`pyproject.toml`、`uv.lock`、`src/mm_final/`、`tests/fixtures/route_plans/`、`tests/test_route_plan_contract.py`、`docs/environment-and-dependencies.md`、`docs/setup-python-env.md`、`docs/changes.md`。

## 2026-06-05  沉淀环境依赖与附加交付分工

- **版本号**：未发布，仍处于第一个可行版本前。
- **问题**：项目即将进入 Python 实现阶段，需要确认依赖配置方式、GUI 起步策略、核心算法依赖、环境配置分支规则，以及 GUI/可视化、书面报告、上台展示三项附加任务分工。
- **解决方案**：
  - 新增 `docs/environment-and-dependencies.md`，记录已确认的 `pyproject.toml` 依赖配置策略、GUI 起步策略、核心算法依赖、共享分支规则和待确认项。
  - 确认可视化依赖栈采用 Matplotlib + NetworkX + Pillow/ImageIO + Plotly，动态展示第一阶段采用静态图 + GIF。
  - 确认依赖声明当前只使用 `pyproject.toml`，并按主依赖、`viz`、`gui`、`dev` 分组。
  - 确认采用 uv 管理环境同步和锁文件；提交 `pyproject.toml`、`uv.lock` 和环境创建说明，不提交 `.venv`。
  - 在 `AGENTS.md` 中补充依赖配置入口和附加交付分工。
  - 在 `docs/implementation-plan.md` 中补充环境与依赖策略、附加交付任务分工和新的待确认问题。
  - 新增 `docs/setup-python-env.md`，说明当前空环境创建方式以及 `pyproject.toml` 建立后的 uv 同步方式。
  - 在 `docs/detailed-plan-for-track-B.md` 中补充 B 线对 GUI 与可视化的职责、实现顺序和风险边界。
- **影响文件**：`AGENTS.md`、`docs/environment-and-dependencies.md`、`docs/setup-python-env.md`、`docs/implementation-plan.md`、`docs/detailed-plan-for-track-B.md`、`docs/changes.md`。

## 2026-06-05  新增 Track B 详细实施计划

- **版本号**：未发布，仍处于第一个可行版本前。
- **问题**：`docs/implementation-plan.md` 面向全局协作，B 线工程师开工前仍缺少聚焦自身工作的细化执行顺序、测试入口、验收标准和风险清单。
- **解决方案**：
  - 新增 `docs/detailed-plan-for-track-B.md`，将 B 线拆分为契约落地、节点分类、方案评价、可行性审计、下界分析、24 小时组数判定、人员足够最短时间、参数敏感性分析等阶段。
  - 明确 B 线的输入、输出、测试建议、验收标准和与 A 线的握手节奏。
  - 强调 B 线不得绕过 `RoutePlan` 契约，不得把候选方案不可行直接等同于组数不可能。
- **影响文件**：`docs/detailed-plan-for-track-B.md`、`docs/changes.md`。

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
