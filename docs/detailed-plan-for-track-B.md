# Track B 详细实施计划

本文档面向 B 线工程师。B 线主责是 **耗时审计、下界证明与参数分析**：判断 A 线或手工候选方案是否合法、是否满足约束，并解释为什么某个组数或完成时间是可信的。

B 线不是 A 线的下游展示层。B 线应在 A 线算法尚未成熟时，用手工方案、小图方案和占位方案先独立推进评价、审计、下界和参数分析。

---

## 0. 开工前约束

### 0.1 Git 分支

建议从最新 `main` 开短生命周期分支：

```powershell
git switch main
git pull
git switch -c b/track-b-bootstrap
```

B 线功能分支命名使用 `b/...`。如果工作中需要修改路线方案契约、公共数据结构或共享测试夹具，不要直接在 `b/...` 分支里夹带修改，应先开 `shared/...` 分支并按 `docs/git-workflow.md` 合并。

### 0.2 不可破坏的契约

B 线所有输入输出必须遵守 `docs/contracts/route-plan-contract.md`：

- 输入方案统一为 `RoutePlan`。
- 单条路线统一为 `Route`。
- 单路线指标统一为 `RouteMetrics`。
- 全方案指标统一为 `PlanMetrics`。
- 审计输出统一为 `AuditResult`。

B 线不得为某个 A 线算法特判解析格式，也不得私自维护另一套路线方案结构。

### 0.3 B 线边界

B 线可以做：

- 读取、校验和评价 `RoutePlan`。
- 复算距离、耗时和完成时间。
- 检查覆盖、重复、路径连通、字段合法性。
- 计算组数下界和完成时间下界。
- 判断给定组数下候选方案是否满足 24 小时。
- 做参数敏感性分析。
- 负责 GUI 与可视化，包括报告图、路线过程动态展示、GIF/无声视频导出和后续轻量 GUI。
- 构造小图、手工路线和占位路线作为测试夹具。

B 线不应该做：

- 主动实现复杂路线构造算法。
- 绕开 A 线生成最终路线。
- 把辅助道路节点当成必访停留点。
- 在没有契约变更流程的情况下改动 `RoutePlan` 字段。
- 将 GUI 状态、控件逻辑或展示格式反向污染后端数学模型。

## 1. B0：契约落地与测试夹具

### 目标

在任何评价或审计逻辑前，先保证 B 线能稳定读取统一方案格式，并拥有可复现测试输入。

### 输入

- `docs/contracts/route-plan-contract.md`
- `data/raw/road_network.tsv`
- 手工构造的最小 `RoutePlan` 样例

### 输出

- 契约数据模型或等价结构。
- 最小手工方案夹具，例如 `manual-smoke-001` 或 `schema-smoke-001`。
- 完整覆盖手工方案夹具，用于后续覆盖审计回归。
- 至少一组非法方案夹具，用于审计错误测试。

### 已拍板决策

1. 公共 `RoutePlan` 数据模型、共享夹具和契约测试先走 `shared/...` 分支，不夹带在 `b/...` 功能分支中；建议分支名为 `shared/route-plan-model` 或同类名称。
2. 契约模型使用标准库 `dataclass` 起步，不引入 Pydantic；后续若 schema 校验复杂再评估额外依赖。
3. 手工方案和非法方案夹具统一使用 JSON 格式。
4. 夹具目录使用 `tests/fixtures/route_plans/`。
5. B0 使用两类手工样例：`schema-smoke` 用于验证字段结构和读取，不要求覆盖全部必访点；`full-coverage-smoke` 用于后续覆盖审计，要求覆盖全部乡镇和村节点。
6. `required_visit_order` 是必访停留节点顺序，不是完整行驶路径。现实路线必须从 `O` 出发并回到 `O`，但 `O` 由 `depot` 和 `expanded_node_path` 表达，不写入 `required_visit_order`。
7. `required_visit_order` 中出现 `O` 时判为 error，不自动删除，也不只给 warning。
8. `required_visit_order` 中出现 `U1`–`U6` 等辅助道路节点时判为 error。
9. Nullable 字段必须保留字段名，暂未计算时写为 `null`；缺少这些字段时判为契约错误。
10. 遇到契约未定义的额外字段时给 warning，并尽量保留原始信息，不静默忽略。
11. 错误诊断内部可使用结构化形式，例如 code、path、message；对外输出仍遵守 `AuditResult.errors` 和 `AuditResult.warnings` 的 `list[string]` 契约。
12. `schema_version` 只接受精确值 `route-plan-v1`。
13. B0 只检查字段结构和基础节点语义，不复算距离和指标；距离、耗时和指标一致性复核留到 B2。
14. 第一批非法夹具至少覆盖四类核心错误：缺必备字段、错误 `schema_version`、`required_visit_order` 含 `O`、`required_visit_order` 含辅助道路节点。
15. 测试框架采用 pytest；由于 pytest 和 `pyproject.toml` 属于共享环境基础，应通过 `shared/...` 分支落地。

### 建议测试

- 能读取 `schema_version = route-plan-v1` 的方案。
- 缺少必要字段或 nullable 字段时能报错。
- `required_visit_order` 中出现 `U1` 等辅助道路节点时能报错。
- `required_visit_order` 中包含 `O` 时能报错，避免把县政府误计入停留。
- `schema-smoke` 样例可用于读取测试，但不得被误标为完整覆盖合法方案。
- 未定义额外字段能产生 warning，且不影响读取已定义字段。

### 验收标准

- B 线不依赖 A 线算法，也能独立跑通契约读取测试。
- 所有测试输入都使用契约字段，不使用临时字符串格式。
- B0 结束时，A/B 两线对 `required_visit_order` 与 `expanded_node_path` 的含义没有歧义。

## 2. B1：路网语义与节点分类复核

### 目标

建立 B 线审计所需的基础语义，确保停留时间和覆盖检查不会出错。

### 输入

- `data/raw/road_network.tsv`
- 题面节点规则：`O`、`A`-`R` 中除 `O` 外的大写字母、`1`-`35`、`U1`-`U6`

### 输出

- 节点类型判定能力。
- 必访节点全集。
- 辅助道路节点集合。
- 路网连通性和边权合法性校验。

### 已拍板决策

1. B1 的节点分类、路网读取、边权校验和连通性校验属于公共底基，先在 `shared/road-network-core` 分支实现并合并到 `main`，不得先在 `b/...` 分支维护 B 线私有版本。
2. 节点集合以题面规则定义语义，以 `data/raw/road_network.tsv` 校验数据完整性；不得完全依赖 TSV 自动推断节点类型。
3. `O` 是县政府所在地和 depot，不属于乡镇节点，也不产生乡镇停留时间。
4. 节点类型使用 `Enum` 表达，例如 `NodeType.DEPOT`、`NodeType.TOWN`、`NodeType.VILLAGE`、`NodeType.AUXILIARY`、`NodeType.UNKNOWN`。
5. 路网对象使用自定义 `RoadNetwork` 包装底层图结构；公共接口保持稳定，不让调用方直接依赖 NetworkX 细节。
6. B1 阶段将 `networkx` 加入主依赖，用于无向加权图、连通性校验，并为后续最短路能力做准备。
7. TSV 读取采用严格校验：表头必须正确，必须只有 `source`、`target`、`weight` 三列，边权必须为正数，节点不得超出题面允许集合。
8. 道路网络建模为无向加权图。
9. 同一无向边在 TSV 中重复出现时判为 error，不自动取较小权重，也不以后出现的值覆盖。
10. 边权使用 `float` 表达，单位为 `km`，合法值必须 `> 0`。
11. 连通性校验要求整个 TSV 图连通，包括 depot、乡镇、村和辅助道路节点。
12. B1 不实现最短路查询或最短路闭包；本阶段只提供节点分类、TSV 读取、图构建、数据校验和连通性校验。最短路能力留到 B2/A1 握手或后续共享分支。
13. 路网校验错误内部使用类似 B0 的结构化诊断表达；可额外提供抛出异常的便利封装，但核心校验结果应能保留多条错误信息。
14. B1 代码放在 `mm_final.network` 包中，不放在 `mm_final.contracts` 或 B 线私有包中。
15. B0 中的 `TOWN_NODES`、`VILLAGE_NODES`、`AUXILIARY_NODES` 等节点常量迁到 `mm_final.network.nodes`；契约模块从共享节点语义中导入复用，避免两边各维护一份。
16. TSV 中出现未知节点，例如 `X`、`36`、`U99`，判为 error。
17. B1 测试固定断言节点数量：乡镇 17、村 35、辅助节点 5、depot 1；并额外测试 `I` 是大写字母 I，不是数字 1。
18. B1 必须检查所有必访节点都出现在正式 TSV 路网中；缺失时判为 error。
19. 辅助节点虽然不属于必访点，但属于道路结构；孤立或不连通的辅助节点由整图连通性校验判为 error。
20. B1 完成边界为：节点分类、TSV 读取、图构建、数据校验、连通性测试；不得扩张到最短路、路线评价器或 B2 内容。
21. 路网读取接口默认读取 `data/raw/road_network.tsv`，同时允许传入自定义 TSV 路径，便于测试非法数据和未来扩展。
22. 非法 TSV 测试夹具放在 `tests/fixtures/road_networks/*.tsv`。
23. `RoadNetwork` 不暴露可变底层图；若需要给 A/B 调试或扩展使用，提供 `to_networkx()` 返回只读语义上的副本。
24. 节点分类函数遇到未知节点时返回 `NodeType.UNKNOWN`，由 TSV 校验阶段将未知节点诊断为 error。
25. 连通性失败时诊断应包含连通分量数量和每个分量的节点集合，方便定位数据问题。
26. 正式 TSV 测试需要固定断言边数等于正式 TSV 数据行数，防止漏读或重复边处理错误。

### 建议测试

- `O` 被识别为县政府所在地，不计入乡镇或村停留。
- `A`、`R` 被识别为乡镇；`I` 是大写字母 I，不是数字 1。
- `1`、`35` 被识别为村。
- `U1`、`U6` 被识别为辅助道路节点。
- 边权必须为正数。
- 原始路网必须连通。
- 正式 TSV 的节点数量、边数、必访节点覆盖和辅助节点集合必须与题面规则一致。
- 非法 TSV 夹具能触发表头错误、未知节点、非正边权、重复无向边和不连通图诊断。

### 验收标准

- 能稳定给出乡镇数量、村数量、辅助节点数量和必访节点数量。
- 节点分类逻辑由测试保护，A/B 两线不会各自解释一套节点语义。
- `RoadNetwork` 能从默认正式 TSV 和自定义 TSV 路径读取。
- B1 不包含最短路查询、耗时评价或路线方案审计逻辑。

## 3. B2：方案评价器

### 目标

对任意合法或近似合法的 `RoutePlan` 复算距离、停留时间、行驶时间和完成时间。

### 评价拆分原则

B2 必须把“评价”拆成两个层次：

- **共享快速评分核心**：面向 A 线内部高频优化调用，保持中性、可复用、尽量纯函数式。它负责最短路、距离闭包、候选解评分、目标函数、邻域操作、方案池和 `CandidateSolution -> RoutePlan` 导出，不负责给出最终审计结论。
- **B 线权威评价与报告复核**：面向阶段性候选方案和最终结果，负责复算指标、生成 warning/diagnostic、对比输入指标和输出报告可用的评价结果。它可以复用共享评分核心，但不得成为 A 线每一步优化的人工或工程阻塞点。

正式合法性判断、覆盖错误、路径错误、下界证明和结论解释仍属于 B3 及后续阶段；B2 只负责把共享评分底座与 B 线评价入口清楚分开。

### 输入

- `RoutePlan`
- 参数 `T_hour`、`t_hour`、`speed_km_per_hour`、`time_limit_hour`
- 路网最短路查询能力

### 输出

- 每条路线的 `RouteMetrics`
- 全方案的 `PlanMetrics`

### 计算口径

- 路线行驶距离：按 `required_visit_order` 中相邻必访点之间的最短路相加，并包括 `O` 到首点、末点回 `O`。
- 行驶时间：`distance_km / speed_km_per_hour`。
- 乡镇停留时间：路线中乡镇节点数乘以 `T_hour`。
- 村停留时间：路线中村节点数乘以 `t_hour`。
- 单路线总耗时：行驶时间加总停留时间。
- 完成时间：所有路线总耗时的最大值。

### 已拍板决策

1. B2 分两段推进：最短路公共接口和 A 线优化所需的最小共享评分底座先走 `shared/shortest-path-core` 或同类 `shared/...` 分支，评价器的审计诊断与报告复核本体再走 `b/...` 分支；最短路、候选解评分和导出能力属于 A/B 共享底基，方案审计解释属于 B 线职责。
2. 最短路接口返回距离和节点路径，推荐结构为 `ShortestPath(distance_km, node_path)`。
3. 最短路方法暴露在 `RoadNetwork` 上，例如 `RoadNetwork.shortest_path(source, target)`，调用方不得绕开封装直接依赖 NetworkX 细节。
4. 公共接口支持单次最短路查询；B2 评价器内部可以缓存 `O` 与所有必访节点之间的最短路闭包。
5. B2 同时计算最短路口径距离和 `expanded_node_path` 口径距离；评价输出以 `required_visit_order` 相邻必访点的最短路口径为准，并对两者差异给出诊断。
6. `required_visit_order` 为空时，B2 允许评价为空路线，距离和耗时为 0，并给出 warning；是否作为合法巡视路线留到 B3 审计。
7. 单路线距离公式固定为 `O -> required_visit_order -> O` 的相邻最短路之和，不信任输入 `distance_km` 作为评价来源。
8. 停留时间只按必访停留节点计算：乡镇乘以 `T_hour`，村乘以 `t_hour`，`O` 和辅助道路节点不产生停留时间。
9. B2 参数优先使用评价器调用时显式传入的值；缺省时再从 `RoutePlan.parameters` 读取。
10. 默认参数使用题面默认值：`T_hour = 2.0`、`t_hour = 1.0`、`speed_km_per_hour = 35.0`、`time_limit_hour = 24.0`，但必须允许覆盖。
11. 参数合法性规则为：`T_hour >= 0`、`t_hour >= 0`、`speed_km_per_hour > 0`、`time_limit_hour > 0`。
12. 评价器不得原地修改输入 `RoutePlan`；应返回新的结构化评价结果。
13. B2 输出结构包含 `route_metrics_by_id`、`plan_metrics` 和 `diagnostics`，不直接返回完整 `AuditResult`。
14. 复用现有 `RouteMetrics` 和 `PlanMetrics` 数据类，新增 B2 私有 `EvaluationResult` 或等价结构；不修改 `RoutePlan` 契约字段。
15. B2 复算输入中已有的 `metrics` 和 `distance_km`，发现不一致时给 warning；正式 error 判定留到 B3 审计器。
16. 浮点容差按字段语义区分：距离容差 `1e-6 km`，时间容差 `1e-6 hour`。
17. B2 内部保留 float 原值，不在后端评价阶段四舍五入；报告和 GUI 展示阶段再格式化。
18. B2 第一阶段只计算契约已有均衡指标：`distance_range_km` 和 `time_range_hour`；标准差、均值、变异系数等统计指标留到后续参数分析或报告层扩展。
19. 单条路线内重复出现必访节点时，B2 按输入顺序复算距离和停留时间，并给 warning；覆盖合法性留到 B3 判断。
20. 跨路线重复节点时，B2 只按每条路线分别复算，不做全局覆盖合法性判断；重复分配错误留到 B3 审计。
21. 若 `expanded_node_path` 相邻节点在正式路网中没有边，B2 对该路线给 diagnostic，但仍按 `required_visit_order` 的最短路口径复算指标。
22. 若输入 `distance_km` 与 B2 复算距离不一致，B2 给 warning，并以复算值作为输出指标。
23. B2 生成每条路线的最短路展开节点序列，作为评价结果的一部分，但不写回输入 `Route.expanded_node_path`。
24. 拼接相邻最短路路径时，去掉后一段首节点，避免段边界出现连续重复节点。
25. B2 测试夹具同时使用正式路网、极小人工路网和已有 B0 JSON 夹具；不等待 A 线方案成熟后再测试。
26. 第一批 B2 测试覆盖单村、单乡镇、两点路线、空路线、含 `expanded_node_path`、输入 metrics 不一致等场景。
27. B2 模块放在 `src/mm_final/evaluation/route_evaluator.py` 或同类 `mm_final.evaluation` 包中，不放在契约模型或临时 B 私有脚本中。
28. B2 阶段不引入新依赖，使用现有 NetworkX 和 Python 标准库完成最短路、距离与指标计算。

### A 线优化接入的最小共享改进

B2 实现时应顺手补齐 A 线后续接入五种经典算法所需的最小共享底座。这里的共享底座服务于 A 线内部高频优化调用，不等同于 B3 之后的权威审计、下界证明和报告解释。

推荐 A 线优先实现的五种经典算法为：

1. `Clarke-Wright savings` 节约算法：用于多路线初解构造。
2. `k-medoids / cluster-first route-second`：用于固定组数下的图距离分组。
3. `2-opt`：用于路线内部访问顺序改进。
4. `relocate` 节点迁移：用于路线之间的负载和距离均衡调整。
5. 模拟退火：用于组合上述邻域操作，跳出局部最优。

为支持以上五种方法，B2 最小共享改进并集为：

- 在 `RoadNetwork` 上提供 `shortest_path()`，返回最短距离和实际节点路径。
- 提供必访节点距离闭包或图距离矩阵，支持路线评分和 `k-medoids` 分组。
- 提供 `CandidateSolution` 或等价内部候选解表示，保存多路线分组、每组访问顺序、算法来源、随机种子和运行参数。
- 提供 `ObjectiveSpec` 与 `Score` 或等价评分结构，统一表达总距离、最大路线距离、距离极差、总耗时、最大路线耗时、超时惩罚等目标。
- 提供路线距离和耗时快速计算能力，允许 A 线在局部搜索中高频调用。
- 提供分组器接口：输入固定组数 `k` 和必访节点集合，输出若干组必访节点；分组器不负责组内访问顺序。
- 提供组内路线构造器接口和组合函数，使“节点组 + 组内路线构造器”能被统一转换为 `CandidateSolution`。
- 提供 `Clarke-Wright` 所需的路线合并后评分能力和候选解轻量检查，但不实现 savings 排序、合并策略或停止条件。
- 提供 `2-opt` 路径反转 primitive，但不实现完整 `2-opt` 搜索策略。
- 提供跨路线 `relocate` primitive，并支持 relocate 后的增量评分或快速重算，但不实现完整 relocate 搜索策略。
- 提供模拟退火可调用的邻域操作集合，至少包含 `relocate`、`swap` 和 `2-opt` move primitive；温度、降温、接受概率和扰动选择由 A 线实现。
- 明确空路线处理策略，避免固定组数算法生成无法解释的占位路线。
- 支持距离均衡和耗时瓶颈两种目标口径，分别服务第 (1) 问和第 (2)–(4) 问。
- 提供 `CandidateSolution -> RoutePlan` 导出器，确保 A 线正式候选方案仍统一进入路线方案契约。
- 提供方案池，至少保存当前最优、若干候选、评分结果、算法参数和随机种子，便于 B 线后续审计比较。

### B2 扩展已拍板决策

以下决策对应 B2 新增共享评分底座后的问题 29 以后内容。核心原则是：B2 负责共享数据结构、评分函数、基础 move primitive、导出器和方案池；五种经典算法的主体由 A 线实现。

29. 共享评分底座后续实现单独开 `shared/scoring-core` 或同类 `shared/...` 分支，不夹带在 B 线私有分支中。
30. 共享评分核心放在 `mm_final.routing` 或同类中性包；`mm_final.evaluation` 保留给 B 线评价器和报告复核入口。
31. B2 评价拆成三层：共享快速评分核心、B 线评价器、B3 可行性审计器。
32. `CandidateSolution` 使用 frozen dataclass 和 tuple 路线表示，便于比较、缓存和测试。
33. `CandidateSolution` 的每条路线只保存必访节点顺序，不保存首尾 `O`；`O` 由评分和导出阶段自动补入。
34. 内部候选解允许暂时非法，但必须通过评分惩罚、轻量诊断或导出前修复机制暴露问题；不得静默导出为正式 `RoutePlan`。
35. 目标函数同时支持词典序目标和加权惩罚目标。
36. `Score` 至少包含距离、耗时、极差、惩罚项和排序 key，不只返回单个 float。
37. 距离闭包覆盖 `O + REQUIRED_VISIT_NODES`；辅助节点作为最短路展开路径中的通行点出现。
38. 距离闭包由单独 `DistanceMatrix` 或等价对象持有，不直接塞进 `RoadNetwork` 内部缓存。
39. 路线距离计算同时返回距离和最短路展开节点路径，服务评价、导出和可视化。
40. 固定组数下允许内部候选解暂时出现空路线；共享评分核心对空路线给 penalty，B2 评价器给 warning，正式合法性由 B3 审计阶段判定。
41. 固定组数 `k` 的候选解必须保持 `k` 条路线；路线数不得在搜索中自动漂移。
42. 分组器接口只返回节点组，不直接返回 `CandidateSolution`；B2 另提供组合函数，将“节点组 + 组内路线构造器”组装成 `CandidateSolution`。
43. 组内路线构造器输入一个必访节点组，输出该组的访问顺序。
44. B2 不实现 `Clarke-Wright savings` 主体；只提供距离闭包、路线合并后的评分函数和候选解轻量检查，A 线负责 savings 排序、合并策略和停止条件。
45. B2 不实现完整 `2-opt` 搜索策略；只提供路线片段反转 primitive 和反转后的评分能力，A 线负责枚举片段、选择 first-improvement 或 best-improvement 以及停止条件。
46. B2 不实现完整 relocate 搜索策略；只提供跨路线单节点迁移 primitive 和迁移后的评分能力，A 线负责选择迁移节点、插入位置和接受策略。
47. B2 提供 `swap` primitive 作为共享基础邻域操作，但不实现完整 swap search。
48. 模拟退火主体归 A 线；B2 只提供 `CandidateSolution`、`ObjectiveSpec`、`Score`、`2-opt`/`relocate`/`swap` move primitive、随机种子记录字段和评分函数。
49. 运行元数据记录 `method`、`parameters`、`seed`、`runtime` 和 `score`。
50. 方案池第一阶段保留 top-n 候选和当前最优，不急于实现复杂非支配前沿。
51. `CandidateSolution -> RoutePlan` 导出时默认保留 `metrics = null`，由 B 线评价器复算；nullable 字段不得省略。
52. 共享评分核心可以产生轻量 `ScoreDiagnostic`，但不得直接产出最终 `AuditResult`。
53. B2 共享底座第一批测试覆盖距离闭包、`CandidateSolution` 评分、导出器、`2-opt`、`relocate` 和方案池。
54. B2 新增共享评分底座阶段不引入额外依赖，继续使用 NetworkX 和 Python 标准库。
55. B2 完成边界为：共享评分底座可被 A 线调用，B 线评价器可复算 `RoutePlan`；不要求 B 线实现五种 A 线算法主体。
56. B2 不实现五种经典算法的主体；B2 只实现共享评分底座、数据结构、move primitive 和导出器。
57. Move primitive 放在 `mm_final.routing.moves` 或同类中性模块，保持 A/B 两线都可复用。
58. A 线算法主体后续放在 `mm_final.routing.algorithms`、`mm_final.routing.solvers` 或 A 线明确命名的同类模块中，不放进 B 线评价器。
59. B2 的 move primitive 不包含最优搜索策略；只负责“给定一个 move，生成新候选并评分”，枚举和选择策略由 A 线实现。
60. B2 不需要掌握 `Clarke-Wright savings`、`k-medoids` 或模拟退火的完整理论细节；只保证这些算法所需的输入输出接口稳定。

### B2 b 段已拍板决策

以下决策对应 B2 的 B 线权威评价与报告复核部分。该部分走 `b/...` 分支，复用共享评分底座，但不实现 A 线算法主体，也不替代 B3 可行性审计器。

61. B2 的 b 段分支名使用 `b/route-plan-evaluator`。
62. B 线评价器模块放在 `mm_final.evaluation.route_plan_evaluator`。
63. B2 评价器入口函数命名为 `evaluate_route_plan()`。
64. B2 评价器输入为 `RoutePlan + RoadNetwork + EvaluationParameters`。
65. 评价参数数据结构命名为 `EvaluationParameters`，不复用共享评分目标 `ObjectiveSpec`。
66. B2 评价结果数据结构命名为 `EvaluationResult`。
67. `EvaluationResult` 至少包含 `plan_id`、`route_metrics_by_id`、`plan_metrics`、`diagnostics` 和 `expanded_paths_by_route_id`。
68. Diagnostic 使用结构化形式：`Diagnostic(code, severity, path, message)`。
69. Diagnostic severity 使用 `info`、`warning`、`error` 三档。
70. B2 可以产生 error 级 diagnostic，用于参数非法或无法复算等阻断评价的问题，但不直接给出最终合法性结论。
71. B2 只负责复算和诊断；B3 负责判定路线方案是否合法。
72. 输入 `metrics` 与复算结果不一致时，B2 给 warning，并使用复算值作为输出。
73. 输入 `distance_km` 与复算结果不一致时，B2 给 warning，并使用复算值作为输出。
74. B2 对输入中已提供的 `RouteMetrics` 和 `PlanMetrics` 字段逐字段比较。
75. 输入 `metrics` 缺失或为 `null` 时，B2 正常复算，不给 warning。
76. B2 在 `EvaluationResult` 中给出补全后的展开路径，不写回输入 `RoutePlan`。
77. 输入 `expanded_node_path` 与复算展开路径不一致时，B2 给 warning，并保留复算展开路径。
78. 输入 `expanded_node_path` 中相邻节点无边时，B2 给 diagnostic，建议 severity 为 `error`，但仍按最短路口径复算路线指标。
79. 空路线在 B2 评价器中输出 warning，指标按 0 计算。
80. 路线内重复必访点时，B2 给 warning，并按出现次数复算停留时间。
81. 跨路线重复必访点时，B2 给 warning，并分别复算各路线。
82. 遗漏必访点时，B2 给 warning；完整覆盖合法性由 B3 审计。
83. B2 计算覆盖摘要，包括 covered、missing 和 duplicated，但不据此给出最终合法性结论。
84. B2 输出包含 `is_within_time_limit`，该字段来自复算后的 `PlanMetrics`。
85. B2 输出瓶颈路线信息。
86. 若多条路线并列瓶颈，B2 输出 `bottleneck_route_ids` 列表。
87. B2 输出距离均衡摘要，除 `distance_range_km` 外，还包含最长路线和最短路线的 route id。
88. B2 输出每条路线的耗时分解，包括行驶时间、乡镇停留、村停留和总停留。
89. B2 核心评价器不自动保存文件，只返回结构化结果。
90. `EvaluationResult` 提供 `to_dict()` 或等价 JSON 序列化辅助。
91. B2 第一版不提供 Markdown 报告函数，Markdown 留给后续报告层。
92. B2 第一批测试覆盖复算距离/耗时、metrics 差异 warning、空路线 warning、展开路径差异和瓶颈路线。
93. B2 b 段测试夹具使用 B0 JSON、小图人工路网和正式路网抽样。
94. B2 b 段不依赖 A 线算法完成，用手工 `RoutePlan` 夹具独立推进。
95. B2 b 段完成标准为：能对手工 `RoutePlan` 输出结构化 `EvaluationResult`，并复算所有指标和诊断；不要求审计最终合法性，也不实现 A 线算法。

### 建议测试

- 单条空必访路线的距离和时间口径必须明确：默认不作为有效巡视路线；如作为占位，应标记 warning。
- 只包含一个村节点的路线：耗时等于 `O` 往返该村最短路行驶时间加 `t_hour`。
- 只包含一个乡镇节点的路线：耗时等于 `O` 往返该乡镇最短路行驶时间加 `T_hour`。
- 路线中包含辅助节点作为展开路径通行点时，不产生停留时间。
- 同一方案中 `metrics` 为空时，B 线可以复算；不为空时，B 线必须复核一致性。

### 验收标准

- 手工 `RoutePlan` 能输出完整 `RouteMetrics` 和 `PlanMetrics`。
- 对第 (1) 问能输出距离均衡指标；对第 (2)-(4) 问能输出耗时瓶颈。

## 4. B3：可行性审计器

### 目标

独立判断一个路线方案是否可用于结果讨论，并给出具体错误。

### 输入

- `RoutePlan`
- 原始路网
- 必访节点全集

### 输出

- `AuditResult`

### 审计规则

字段审计：

- `schema_version` 必须合法。
- `plan_id`、`source`、`routes` 必须存在。
- 每条 `Route` 必须有 `route_id`、`depot`、`required_visit_order`。

覆盖审计：

- 所有乡镇和村节点必须被覆盖。
- 必访节点不得遗漏。
- 必访节点不得被多条路线重复分配。
- 辅助道路节点不得出现在 `required_visit_order`。

路径审计：

- `depot` 必须为 `O`。
- 若 `expanded_node_path` 存在，首尾必须为 `O`。
- 若 `expanded_node_path` 存在，相邻节点必须在原始路网中可达或能被解释为最短路展开结果。
- 距离字段若存在，必须与 B 线复算值在容差内一致。

### 已拍板决策

1. B3 本体走 `b/route-plan-auditor` 分支；只有路线方案字段、单位、节点语义、共享测试夹具或公共审计口径变化时，才切到 `shared/...` 分支。
2. B3 模块放在 `mm_final.evaluation.route_plan_auditor`，不放在契约模型或路线构造包中。
3. B3 核心入口命名为 `audit_route_plan(plan, road_network, parameters=None, mode=...) -> AuditResult`；可额外提供读取 JSON 或处理读取结果的轻量 helper。
4. B3 必须复用 B2 的 `evaluate_route_plan()` 进行指标复算和诊断分类，不重新实现距离、耗时和覆盖摘要计算，也不信任输入 `metrics` 作为审计来源。
5. B3 第一版直接支持 `candidate` 和 `final` 两种模式；`candidate` 用于 A 线中间候选方案诊断，`final` 用于可进入结果讨论的严格终审。
6. 空路线在 `final` 模式下判为 error；如后续 A 线方案池需要占位路线，由 `candidate` 模式或显式参数承接，不把空路线默认为合法最终路线。
7. 遗漏必访点、跨路线重复必访点和单路线内重复必访点在 `final` 模式下均使 `coverage_valid = false`。
8. `expanded_node_path` 若存在，首尾必须为 `O`，相邻节点必须是原始路网真实边；由于最短路可能并列，提供路径与 B2 复算最短路展开不完全一致时先给 warning，不默认判为路径错误。
9. 已提供的 `distance_km`、`Route.metrics` 或 `Plan.metrics` 与 B2 复算值不一致时，在 `final` 模式下使 `metric_valid = false`；对应字段为 `null` 时不处罚。
10. 24 小时上限不属于 B3 的路线合法性；B3 可保留 B2 复算出的 `is_within_time_limit`，但最少组数与超时结论留给 B5。
11. `route_id` 必须在同一 `RoutePlan` 内唯一；重复 `route_id` 判为 error，避免 B2 的 `route_metrics_by_id` 无法稳定表达每条路线。
12. 参数来源沿用 B2 口径：显式参数优先，其次读取 `RoutePlan.parameters`，最后使用题面默认值。
13. B3 内部可继续使用 `Diagnostic(code, severity, path, message)` 分类；对外输出仍遵守 `AuditResult.errors` 和 `AuditResult.warnings` 的 `list[string]` 契约，不为 B3 第一版修改 `AuditResult` 字段。
14. B3 第一批测试优先用代码构造小图和 `RoutePlan`，覆盖合法方案、遗漏节点、重复节点、空路线、坏展开路径、指标不一致和重复 `route_id`；若新增可复用 JSON 夹具，应先确认是否属于共享契约夹具。
15. 无法解析的方案通过 helper 进入 B3 文件级审计：核心 `audit_route_plan()` 只接收已解析的 `RoutePlan`，另提供 helper 接收 `ValidationResult` 或 JSON 路径；解析失败时 helper 返回 `schema_valid = false` 的 `AuditResult`。
16. `candidate` 模式的降级清单为：schema 错误和展开路径坏边仍为 error；覆盖遗漏、重复、空路线和 metrics 不一致降级为 warning，用于 A 线中间方案修复。
17. B3 第一版不修改 `AuditResult` 契约来新增机器可读的 `mode` 字段；在 warning、error 或 Markdown 摘要中标注 `candidate` 审计不等于最终审计。
18. 若后续 GUI、报告生成器或批量审计仪表盘需要自动过滤、排序或门禁不同审计模式，例如只把 `final` 审计写入正式结论、只在调试区展示 `candidate` 审计、按模式统计错误率或避免把候选方案误发布，再走 `shared/...` 评估是否给 `AuditResult` 增加机器可读 `mode` 字段。
19. B3 同时生成 Markdown 审计摘要，用于人工分析、A/B 沟通和报告草稿；Markdown 是结构化 `AuditResult` 的派生视图，不替代 `AuditResult`，也不承载额外数学口径。

### 建议测试

- 遗漏一个村节点时，错误信息必须指出具体节点。
- 重复分配一个乡镇节点时，错误信息必须指出节点和路线。
- `required_visit_order` 出现 `U3` 时必须报错。
- 路线未返回 `O` 时必须报错。
- `distance_km` 与复算结果不一致时必须报错或至少 warning。
- `candidate` 模式下覆盖遗漏、重复、空路线和 metrics 不一致应进入 warning，不应阻断中间候选方案诊断。
- `final` 模式下同类问题应使对应有效性字段为 false。
- Markdown 审计摘要应从 `AuditResult` 和 B2 复算结果派生，并明确标注候选审计或最终审计口径。

### 验收标准

- A 线给出的任何候选方案都可以被 B 线审计。
- 审计结果可用于指导 A 线修复，而不是只返回 True/False。

### 已落地能力

- `mm_final.evaluation.route_plan_auditor` 提供 `audit_route_plan()`、`audit_validation_result()`、`audit_route_plan_json()` 和 `audit_result_to_markdown()`。
- 核心审计器复用 B2 `evaluate_route_plan()`，将覆盖、路径、指标和 schema 诊断分类为 `AuditResult` 的四类有效性字段、错误列表和警告列表。
- `candidate` 模式用于中间方案诊断，`final` 模式用于正式结果终审；Markdown 摘要由结构化审计结果派生，服务人工复核与报告草稿。

## 5. B4：组数下界与不可能性分析

### 目标

为第 (2) 问和第 (3) 问提供“为什么至少需要这么多组”或“为什么完成时间不可能更短”的解释。

### 输入

- 节点停留时间参数 `T_hour`、`t_hour`
- 车速 `speed_km_per_hour`
- 时间上限 `time_limit_hour`
- 最短路距离

### 输出

- 对每个候选组数 `k` 的下界报告。
- 对无限人手最短完成时间的下界报告。

### 推荐下界

总服务时间容量下界：

- 全部乡镇停留时间加全部村停留时间是必须负载。
- 若要在 `H` 小时内完成，组数至少满足 `k >= total_stop_time / H`。
- 该下界不含行驶时间，因此只是不可能性筛查的弱下界。

单点往返下界：

- 每个必访节点单独巡视也至少需要 `2 * dist(O, node) / v + stop_time(node)`。
- 全方案完成时间不可能小于所有单点往返下界的最大值。

路线容量下界：

- 对固定 `k`，若某些远端或高停留负载节点集合无论如何都无法塞入 `k` 条路线的时间容量，应给出集合级下界。
- 初期可以先做可解释的简单集合下界，不急于做复杂证明。

### 已拍板决策

1. B4 本体走 `b/lower-bound-analysis` 分支；只有新增公共数据结构或共享契约字段时才切到 `shared/...` 分支。
2. B4 模块放在 `mm_final.evaluation.lower_bounds`，不放在 `mm_final.routing` 或 `mm_final.contracts` 中。
3. B4 输出结构命名为 `LowerBoundReport` 或等价数据类，提供 `to_dict()` 和 Markdown 摘要 helper，便于 B5/B6 机器读取和报告引用。
4. B4 第一版不修改 `RoutePlan`、`AuditResult` 或 `PlanMetrics` 契约；下界报告是方案外的证明材料。
5. B4 只计算下界和不可能性证据；B5 负责把下界、A 线候选方案池和 B3 审计结果合成为最少组数判定。
6. 候选组数范围由调用方显式传入 `k_values`；B4 可提供默认范围 helper，但不在核心函数中自动猜测扫描范围。
7. 参数通过 `LowerBoundParameters` 或等价结构显式传入，默认题面参数为 `T_hour=2.0`、`t_hour=1.0`、`speed_km_per_hour=35.0`、`time_limit_hour=24.0`。
8. B4 第一版下界组合为：总停留时间容量下界、单点往返下界和简单集合负载下界。
9. 总停留时间容量下界使用 `ceil(total_stop_time / H)` 给出最少组数弱下界；不加入未经证明的估计行驶时间。
10. 单点往返下界使用 `2 * dist(O, node) / v + stop_time(node)`；不得用 A 线候选路线距离替代该下界。
11. 固定 `k` 的完成时间下界第一版以 `max(total_stop_time / k, max_single_node_round_trip)` 为基线；若集合负载下界被标注为 `strict/provable`，也可纳入该 `k` 的强排除计算。
12. 简单集合负载下界第一版只覆盖可解释的小集合，例如远端节点 Top-N、乡镇集合、村集合和按 depot 距离分层集合；不枚举所有子集。
13. 只有严格数学成立的集合下界才能用于标记某个 `k` 为不可能；启发式或经验性集合分析只能作为解释或筛查，不能作为强排除依据。
14. 不可能性状态使用结构化命名：`lower_bound_impossible`、`not_excluded`、`insufficient_evidence`。
15. B4 第一版不读取 A 线候选方案池；候选方案池与上界差距对比留给 B5。
16. B4 第一版不依赖 B3 审计结果；下界可以在没有候选方案时独立计算。
17. B4 计算通用的无限人手最短完成时间下界，B6 使用该下界回答第 (3) 问，不由 B4 直接给第 (3) 问最终结论。
18. 内部计算保留 float 原值；下界比较使用小容差，组数下界只对组数做 `ceil`，展示格式留给 Markdown 或报告层。
19. B4 测试使用小图人工路网、正式路网 smoke 和手算案例；不等待 A 线结果。
20. B4 输出同时提供结构化 `LowerBoundReport` 和 Markdown 摘要。
21. 每个下界条目必须标注强弱类型，例如 `strict/provable`、`screening_only` 或 `heuristic`，避免把筛查性弱下界误写成强证明。
22. B4 第一版完成标准为：能对给定参数和 `k_values` 输出可测试的下界报告，并能标记被严格下界排除的 `k`；不要求证明最终最少组数，也不要求构造路线。

### 当前落地接口

- `mm_final.evaluation.lower_bounds` 提供 `LowerBoundParameters`、`LowerBoundEntry`、`GroupLowerBound`、`LowerBoundReport`、`compute_lower_bound_report()`、`default_k_values()` 和 `lower_bound_report_to_markdown()`。
- `compute_lower_bound_report(road_network, k_values=..., parameters=...)` 是 B4 核心入口；调用方必须显式给出 `k_values`，参数缺省时使用题面默认值。
- `LowerBoundReport.group_bounds` 对每个 `k` 输出完成时间下界、状态和触发该下界的证据 code；`LowerBoundReport.bound_entries` 保留可解释证据并标注 `strict/provable` 或 `screening_only`。
- 当前 `group_bounds` 只使用 `strict/provable` 证据执行强排除；距离分层集合保留为 `screening_only` 报告项，不参与 `lower_bound_impossible` 判定。
- `unlimited_personnel_lower_bound_hour` 当前取所有必访节点单点往返下界的最大值，供 B6 作为第 (3) 问的通用下界输入。

### 建议测试

- 总服务时间下界可由已知乡镇数量、村数量直接复核。
- 单点往返下界对若干节点可人工复核。
- 当下界已经超过 24 小时时，对应组数必须判为不可能。

### 验收标准

- 能区分“候选方案不可行”和“该组数理论上已被下界排除”。
- 下界输出可直接进入最终报告解释。

## 6. B5：24 小时最少组数判定

### 目标

主攻第 (2) 问：给定 `T=2h`、`t=1h`、`v=35km/h`，判断至少需要几组，并审计该组数下的推荐路线。

### 输入

- A 线对不同 `k` 生成的候选方案池。
- B 线下界结果。
- 时间上限 `24h`。

### 输出

- 每个 `k` 的判定记录。
- 最少可行组数。
- 最少组数下的推荐方案审计结果。

### 判定流程

1. 从 `k=1` 开始。
2. 先计算理论下界；若下界已经超过 24 小时，直接标记该 `k` 不可能。
3. 若下界未排除该 `k`，审计 A 线候选方案池。
4. 对合法候选方案复算完成时间。
5. 若存在完成时间不超过 24 小时的合法方案，则该 `k` 可行。
6. 若没有可行方案但下界未排除，应标记为“需要 A 线继续搜索或需要更强下界”，不能直接宣称该 `k` 不可能。

### 已拍板决策

1. B5 本体走 `b/minimum-group-decision` 分支；只有新增跨线候选池契约时才切到 `shared/...` 分支。
2. B5 模块放在 `mm_final.evaluation.minimum_group_count`，不放在 `mm_final.routing` 或 `mm_final.contracts` 中。
3. B5 输出结构命名为 `MinimumGroupReport`、`GroupDecisionRecord` 和 `CandidateDecisionRecord` 或等价数据类，提供 `to_dict()` 和 Markdown 摘要 helper。
4. B5 第一版不修改 `RoutePlan`、`AuditResult` 或下界数据结构契约；B5 结论是方案外判定材料。
5. B5 核心入口接收 `candidate_plans_by_k: Mapping[int, Iterable[RoutePlan]]`；`SolutionPool` 只通过 adapter/helper 转换为 `RoutePlan` 后进入 B5。
6. B5 第一版不定义新的 candidate-pool JSON envelope，只加载多个 `RoutePlan` JSON 并按 `k` 归组；该 envelope 不是后续必做项，可以长期不做。只有当多算法、多目录、跨进程或 GUI 批量交换需要统一元数据时，才走 `shared/...` 讨论候选池文件契约。
7. 候选组数范围由调用方显式传入 `k_values`，B5 可提供默认范围 helper，但核心函数不只扫候选池中出现的 `k`。
8. B5 对所有给定 `k` 都生成判定记录，`minimum_feasible_k` 取最小可行组数；不因遇到第一个可行方案就停止记录。
9. 参数通过 `MinimumGroupParameters` 或等价结构显式传入，并统一派生 B3 `EvaluationParameters` 与 B4 `LowerBoundParameters`；若候选 `RoutePlan.parameters` 与统一参数不一致，只记录 warning，不改变本批判定口径。
10. B5 可接收已有 `LowerBoundReport`，没有则内部调用 B4；若传入报告未覆盖所有 `k_values`，应返回错误或诊断。
11. B4 状态映射为：`lower_bound_impossible` 直接强排除；`not_excluded` 和 `insufficient_evidence` 继续审计候选池。
12. B5 只使用 B3 `final` 模式作为候选进入正式结论的审计门禁。
13. 候选可行条件为：B3 的 `schema_valid`、`coverage_valid`、`route_valid`、`metric_valid` 全为真，`recomputed_metrics` 存在，`group_count == k`，且 `is_within_time_limit=True`。
14. 若候选路线条数不等于当前 `k`，记录 `candidate_group_count_mismatch`，该候选不可作为该 `k` 的上界；不自动挪到别的 `k`。
15. 每个 `k` 的状态使用结构化枚举：`lower_bound_impossible`、`candidate_feasible`、`candidate_not_found`、`candidate_invalid`、`insufficient_evidence`。
16. 最少组数结论等级区分 `proven_minimum`、`incumbent_minimum` 和 `no_feasible_candidate`；若更小 `k` 未被下界强排除，只能说当前候选最小，不能说数学最少。
17. “最佳路线”排序先过滤 final-valid 且 24 小时内候选，再按 `completion_time_hour`、`total_distance_km`、`time_range_hour`、`distance_range_km`、`plan_id` 排序。
18. 只有最佳合法且 24 小时内候选形成 feasible upper bound；最佳合法但超时的候选只记录为 observed candidate time，不构成可行上界。
19. 每个 `k` 记录 `lower_bound_hour`、`best_candidate_time_hour` 和 `gap_hour`；不可得字段用 `null` 或等价空值表示。
20. A 线搜索完成声明第一版只作为 `search_complete` 元信息记录，不作为数学证明，也不能据此排除未被下界强排除的 `k`。
21. 重复 `plan_id` 记录 warning，仍逐个审计，内部使用稳定序号区分候选记录。
22. B5 核心只接已解析 `RoutePlan`；文件 helper 负责把解析失败的 JSON 转成 invalid 的 `CandidateDecisionRecord`。
23. B5 第一版不使用 B2/共享 `score_candidate()` 预筛，所有候选都走 B3 final。若候选池规模很大，可增加可选预筛层，但预筛只能用来排序、分批或截取进入终审的候选，不能替代 B3 final，也不能直接形成可行性或最少组数结论。
24. B5 输出结构化 `MinimumGroupReport` 和 Markdown 摘要。
25. B5 测试使用小图手算，覆盖下界排除、候选可行、候选超时、候选非法、缺候选和正式路网 smoke；不等待 A 线结果。
26. `MinimumGroupReport` 只引用最佳候选的 `plan_id` 和 `AuditResult`，不复制完整 `RoutePlan`；完整路线仍由原始 `RoutePlan` 文件或对象承载。
27. B5 第一版完成标准为：能对给定 `k_values` 和候选池输出每个 `k` 的判定、最小候选可行 `k`、结论等级、上下界差距和 Markdown 摘要；不要求证明数学最少组数，也不生成路线。

### 当前落地接口

- `mm_final.evaluation.minimum_group_count` 提供 `MinimumGroupParameters`、`CandidateDecisionRecord`、`GroupDecisionRecord`、`MinimumGroupReport`、`decide_minimum_group_count()`、`decide_minimum_group_count_json_files()`、`default_minimum_group_k_values()` 和 `minimum_group_report_to_markdown()`。
- `decide_minimum_group_count(road_network, k_values=..., candidate_plans_by_k=..., parameters=...)` 是 B5 核心入口，只接已解析的 `RoutePlan`。
- `decide_minimum_group_count_json_files(...)` 是文件 helper，接收按 `k` 归组的 RoutePlan JSON 路径；解析失败的文件会进入 invalid `CandidateDecisionRecord`，不污染核心入口。
- `MinimumGroupReport.conclusion_status` 使用 `proven_minimum`、`incumbent_minimum` 或 `no_feasible_candidate`；只有所有更小正整数 `k` 都被下界强排除时，才输出 `proven_minimum`。
- `GroupDecisionRecord.best_candidate_time_hour` 表示当前 `k` 下已通过 final 审计且组数匹配的最佳观测候选耗时；`feasible_upper_bound_hour` 只有该候选同时满足 24 小时时才存在。

### 继承 B4 的待接事项

- 读取 B4 的 `LowerBoundReport`，将每个 `k` 的 `lower_bound_impossible`、`not_excluded`、`insufficient_evidence` 状态纳入最少组数判定记录。
- 对每个未被下界排除的 `k`，再读取 A 线候选方案池并调用 B3 final 审计；B5 才负责比较候选方案完成时间和 24 小时上限。
- 计算并报告上下界差距：B4 下界作为 lower bound，A 线最优可行候选作为 upper bound。只有上下界合拢时，才能宣称该组数或完成时间结论具有强证明。
- 若 B4 只给出 `screening_only` 或 `heuristic` 说明，B5 不得据此排除组数，只能记录为需要更强下界或继续搜索。
- B4 不读取候选池这一点由 B5 接住；候选池排序、最佳候选选择和失败原因分类都在 B5 完成。

### 验收标准

- 对每个 `k` 都有明确状态：`lower_bound_impossible`、`candidate_feasible`、`candidate_not_found`。
- 最终结论同时包含路线审计和下界解释。

## 7. B6：人员足够时最短完成时间

### 目标

主攻第 (3) 问：在人员足够多时，找出完成巡视的最短时间，并解释对应路线为什么可信。

### 输入

- 单点往返下界。
- A 线或手工生成的多组候选路线。
- B 线评价器和审计器。

### 分析流程

1. 计算所有必访节点的单点往返耗时下界。
2. 找到当前最强的完成时间下界。
3. 构造或接收能达到该下界附近的候选方案。
4. 检查合并近邻节点是否降低最大完成时间，避免机械地每点一组。
5. 若候选方案完成时间等于下界，形成强结论。
6. 若候选方案高于下界，记录差距，并说明仍需 A 线或更强分析推进。

### 已拍板决策

1. B6 本体走 `b/unlimited-personnel-time` 分支；只有新增共享契约字段时才切到 `shared/...` 分支。
2. B6 模块放在 `mm_final.evaluation.unlimited_personnel_time`，不放在 `mm_final.routing` 或 `mm_final.contracts` 中。
3. B6 输出结构命名为 `UnlimitedPersonnelReport` 和 `ShortestTimeCandidateRecord` 或等价数据类，提供 `to_dict()` 和 Markdown 摘要 helper。
4. B6 第一版不修改 `RoutePlan`、`AuditResult` 或下界数据结构契约；B6 结论是方案外证明与推荐材料。
5. B6 自动生成 `singleton_certificate` 基线：每个必访点一条路线，用于证明上界等于 B4 单点往返下界。
6. B6 与 A 线边界为：B6 生成证明基线并审计候选，A 线负责提供更优 secondary objective 的等最短时间候选。
7. B6 核心入口接收 `candidate_plans: Iterable[RoutePlan]`，不按 `k` 归组，也不直接接收 `SolutionPool`。
8. B6 文件 helper 第一版加载多个 `RoutePlan` JSON，不定义新的 unlimited-time candidate-pool envelope。
9. 参数通过 `UnlimitedPersonnelParameters` 或等价结构显式传入，包含 `T_hour`、`t_hour`、`speed_km_per_hour`、`required_visit_nodes` 和 `time_tolerance_hour`。
10. 24 小时上限不作为 B6 候选合法性条件；它只可作为审计指标或展示参考，因为第 (3) 问讨论的是最短完成时间。
11. B6 优先接收已有 `LowerBoundReport`，没有则内部调用 B4，并使用 `unlimited_personnel_lower_bound_hour` 作为第 (3) 问 lower bound。
12. 最短时间结论等级使用 `proven_shortest_time`、`incumbent_shortest_time` 和 `no_valid_candidate`。
13. 候选进入推荐的合法性条件为：B3 final 审计四类 valid 全真且 `recomputed_metrics` 存在；不要求 `is_within_time_limit=True`。
14. `completion_time_hour <= lower_bound_hour + tolerance` 视为等最短时间候选。
15. 推荐路线排序先筛等最短时间候选，再按 `group_count`、`total_distance_km`、`time_range_hour`、`distance_range_km`、`plan_id` 排序。
16. 单点一组基线可作为兜底推荐，但应以 `singleton_certificate` 状态标记为证明基线；若存在等最短时间且更少组的候选，优先推荐该候选。
17. B6 第一版不搜索近邻合并，只审计 A 线或手工合并候选，并在报告中记录 secondary objective 改进空间。
18. B6 不以 B5 为核心，只复用 B3 final 审计和 B4 下界；B5 的 24 小时最少组数判定不适合包装成 B6。
19. 候选状态使用结构化枚举：`optimal_time_candidate`、`valid_slower_candidate`、`candidate_invalid`、`parse_failed`、`singleton_certificate`。
20. B6 记录 `lower_bound_hour`、`best_completion_time_hour` 和 `gap_hour`；有 singleton 基线时 gap 应为 0。
21. 默认允许最多必访点数条非空路线；B3 final 的覆盖与空路线规则会约束候选，不把路线数固定为 B5 最少组数。
22. 重复 `plan_id` 记录 warning，仍逐个审计，内部使用稳定序号区分候选记录。
23. 若候选 `RoutePlan.parameters` 与 B6 显式参数不一致，按 B6 参数重算并记录 warning。
24. B6 核心只接已解析 `RoutePlan`；文件 helper 负责把解析失败 JSON 转成 invalid candidate record。
25. `UnlimitedPersonnelReport` 引用推荐 `plan_id`、候选记录和审计结果；singleton baseline 可由 helper 另行生成，不把完整 `RoutePlan` 嵌入报告。
26. B6 输出结构化 `UnlimitedPersonnelReport` 和 Markdown 摘要。
27. B6 测试使用小图手算，覆盖单点下界、singleton 证明、等最短候选优先、合法但更慢候选、非法候选、JSON 解析失败和正式路网 smoke；不等待 A 线输出。
28. B6 第一版完成标准为：能输出被证明的最短完成时间、推荐等最短时间路线记录、上下界差距、结论等级和 Markdown 摘要；不要求 A 线复杂优化完成。
29. B7 复用 B6 参数化最短时间分析，扫描 `T`、`t`、`v` 对最短时间值和瓶颈节点的影响；该接续事项必须写入 B7 计划。

### 当前落地接口

- `mm_final.evaluation.unlimited_personnel_time` 提供 `UnlimitedPersonnelParameters`、`ShortestTimeCandidateRecord`、`UnlimitedPersonnelReport`、`build_singleton_certificate_plan()`、`analyze_unlimited_personnel_time()`、`analyze_unlimited_personnel_time_json_files()` 和 `unlimited_personnel_report_to_markdown()`。
- `analyze_unlimited_personnel_time(road_network, candidate_plans=..., parameters=...)` 是 B6 核心入口，只接已解析的 `RoutePlan`，并自动把 `singleton_certificate` 记录放入候选记录。
- `analyze_unlimited_personnel_time_json_files(...)` 是文件 helper，接收多个 RoutePlan JSON 路径；解析失败会进入 `parse_failed` 候选记录，不污染核心入口。
- `build_singleton_certificate_plan(parameters=...)` 可单独生成单点一组 `RoutePlan`，供报告附件或后续可视化复用。
- `UnlimitedPersonnelReport` 记录 `shortest_time_lower_bound_hour`、`best_completion_time_hour`、`gap_hour`、`recommended_plan_id`、`recommended_status`、`bottleneck_node` 和所有候选记录；若 singleton 基线有效，通常给出 `proven_shortest_time`。

### 继承 B4 的待接事项

- 使用 B4 给出的无限人手最短完成时间通用下界，作为第 (3) 问的 lower bound。
- 接收 A 线或手工构造的候选路线作为 upper bound，并通过 B3 final 审计确认候选路线合法。
- 判断候选完成时间是否与 B4 下界合拢；若合拢，形成强结论；若未合拢，只能报告当前候选值、下界来源和剩余差距。
- B4 不直接回答第 (3) 问最终结论这一点由 B6 接住；B6 负责说明最短完成时间下需要多少组、路线结构如何、以及是否仍需更强分析。
- 若近邻节点合并能降低最大完成时间，B6 负责让 A 线或手工构造候选方案验证，不回退到 B4 做路线搜索。

### 继承到 B7 的待接事项

- B7 参数敏感性分析应复用 B6 的参数化最短时间分析能力，扫描 `T`、`t`、`v` 改变时最短完成时间值、瓶颈节点和单点一组基线结构如何变化。
- B7 若比较不同参数下的候选路线，应继续使用 B3 final 审计与 B6 的上下界差距口径，不把启发式候选值写成强最优结论。

### 验收标准

- 输出最短完成时间候选值。
- 输出达到该时间的路线组。
- 说明最短完成时间的下界来源和候选方案差距。

## 8. B7：参数敏感性分析

### 目标

主攻第 (4) 问：固定组数时，分析 `T`、`t`、`v` 改变对最佳巡视路线的影响。

B7 第一版定位为“参数情景审计与敏感性报告层”，不是 A 线重优化器。它对给定的一批代表性 `RoutePlan` 候选，在不同参数情景下统一重算、终审、排序和解释，回答完成时间、瓶颈路线、停留/行驶占比和路线结构重构需求如何变化。若要宣称某个参数情景下的全局最优，必须接入 B5/B6 或 A 线额外候选形成证明，B7 本身不把候选池最优偷换成数学最优。

### 输入

- 固定组数，默认优先分析 3 组。
- 若干代表性路线方案。
- 参数集合或参数网格。

### 建议参数设计

- `T`：围绕 2 小时上下变化，用于观察乡镇节点影响。
- `t`：围绕 1 小时上下变化，用于观察村节点数量影响。
- `v`：围绕 35 km/h 上下变化，用于观察行驶距离权重影响。

### 输出

- 不同参数下的完成时间。
- 瓶颈路线变化。
- 乡镇停留、村停留、行驶时间三部分占比变化。
- 路线结构是否需要重新分组的解释。

### 分析重点

- 当 `v` 很高时，停留时间主导，分组更接近按节点服务负载均衡。
- 当 `v` 很低时，行驶距离主导，分组更应重视空间邻近性。
- 当 `T` 增大时，乡镇节点集中的路线更可能成为瓶颈。
- 当 `t` 增大时，村节点数量多的路线更可能成为瓶颈。

### 已拍板决策

1. B7 本体走 `b/parameter-sensitivity-analysis` 分支；只有新增共享参数契约或跨线文件 envelope 时才切到 `shared/...` 分支。
2. B7 模块放在 `mm_final.evaluation.parameter_sensitivity`，不放在 `mm_final.routing` 或 `mm_final.contracts` 中。
3. B7 输出结构命名为 `SensitivityReport`、`ParameterScenario` 和 `ScenarioEvaluationRecord` 或等价数据类，提供 `to_dict()`、Markdown 摘要和表格行 helper。
4. B7 第一版不修改 `RoutePlan`、`AuditResult`、B4、B5 或 B6 的既有契约结构；参数敏感性结论是方案外分析材料。
5. B7 核心入口接收 `candidate_plans: Iterable[RoutePlan]` 和显式 `ParameterScenario` 列表；A 线 `SolutionPool` 和文件目录只通过 adapter/helper 转换后进入核心。
6. 文件 helper 第一版加载多个 `RoutePlan` JSON 和独立情景配置，不定义新的 sensitivity-pool JSON envelope。
7. B7 不做路线重优化，只评估固定候选路线结构，并在报告中标记 `requires_reoptimization` 或等价重优化提示。
8. A/B 握手方式为：A 线在关键参数情景下补充或重构候选路线，B7 负责审计、比较和解释；B7 不反向承担 A 线搜索职责。
9. 参数情景由调用方显式传入，B7 可提供默认代表性情景 helper，但核心函数不隐式密集扫描全空间。
10. 默认基准参数使用题面口径：`T_hour=2.0`、`t_hour=1.0`、`speed_km_per_hour=35.0`。
11. 默认代表性情景以单因素扰动为主，例如 `T={1.5,2.0,2.5}`、`t={0.5,1.0,1.5}`、`v={25,35,45}`，并可额外加入少量组合情景；第一版不做三维笛卡尔密集全扫。
12. 固定组数分析默认优先 3 组，同时允许候选包含其他组数并分组展示，不强制丢弃非 3 组候选。
13. 每个候选在每个参数情景下都调用 B3 `final` 审计，并通过显式参数重算指标；B7 不信任候选原始 metrics。
14. 24 小时上限在 B7 中默认作为展示和状态字段，不作为参数敏感性候选合法性的硬门槛；若要重新判断 24 小时最少组数，应交给 B5。
15. 候选进入正式比较的条件为：B3 final 的 `schema_valid`、`coverage_valid`、`route_valid`、`metric_valid` 全为真，且存在复算指标；warning 不必自动剔除。
16. 每个情景下的推荐候选排序先按 `completion_time_hour`，再按 `total_distance_km`、`time_range_hour`、`distance_range_km` 和 `plan_id`。
17. 内部计算保留 float 原值，排序、delta 和等值判断使用小容差；报告展示阶段再格式化。
18. 敏感性指标至少记录相对基准情景的完成时间变化、总路程变化、瓶颈路线变化、停留/行驶占比变化和候选排名变化。
19. 瓶颈分析复用 B2/B3 复算得到的 route metrics、`bottleneck_route_ids` 和路线级耗时分解，不在 B7 中另起一套耗时口径。
20. 停留/行驶分解按路线记录 travel time、town stop time、village stop time 及其占比，用于解释 `T`、`t`、`v` 的影响来源。
21. 路线结构变化判断只作为 `screening_only` 信号，例如候选赢家变化、瓶颈路线切换、完成时间增幅过大或耗时均衡明显恶化；不得作为全局最优或不可能性的数学证明。
22. 默认重优化提示阈值为：相对基准完成时间增幅超过 10%、`time_range_hour` 超过 1 小时、瓶颈路线切换或情景赢家变化；阈值应可配置。
23. 情景结论等级区分 `best_in_pool`、`needs_reoptimization`、`proven_by_b5_or_b6` 和 `no_valid_candidate` 或等价状态，明确候选池最优不等于数学最优。
24. B7 可选复用 B5，用于某些参数情景下重新判断 24 小时最少组数；这不是 B7 核心路径。
25. B7 应复用 B6 参数化最短时间分析能力，给出每个情景下无限人手最短完成时间、瓶颈节点和单点一组基线变化摘要。
26. B7 可选调用 B4/B6 展示 lower/upper gap；没有证明时只展示候选池观测结果，不硬写强最优。
27. 第一版不使用 B2/共享 `score_candidate()` 预筛，所有候选全量审计；候选池很大时可后续增加只影响审计顺序和批量的 Top-N 预筛。
28. 重复 `plan_id` 记录 warning，内部使用稳定序号区分记录，不直接阻断情景审计。
29. 若候选 `RoutePlan.parameters` 与当前 `ParameterScenario` 不一致，按情景参数重算并记录 warning。
30. B7 核心只接已解析 `RoutePlan`；文件 helper 负责把解析失败的 JSON 转成 invalid scenario record。
31. B7 输出结构化 `SensitivityReport`、Markdown 摘要和表格行数据；CSV、图片和交互图表导出留给 B8 或报告层。
32. B7 只输出可画图数据，不直接承担图表和 GUI；B8 负责路线图、指标图、动态展示和交互展示。
33. B7 测试使用小图手算，覆盖参数扰动、瓶颈切换、候选排名变化、非法候选、Markdown 和表格行输出；再加正式路网 smoke，不等待 A 线最终结果。
34. B7 第一版完成标准为：能对候选池和参数情景输出每情景审计排名、敏感性 delta、瓶颈变化、停留/行驶分解、重优化提示、可选 B5/B6 证明摘要和 Markdown；不要求完成全局重优化、GUI 或图表绘制。

### 继承 B6 与交给 B8 的事项

- 继承 B6 的参数化最短时间分析：对每个 `ParameterScenario`，可复用 B6 生成无限人手最短完成时间、瓶颈节点和单点一组基线摘要。
- 继承 B5/B6 的强结论口径：只有 B5/B6 或其他严格上下界证明支撑时，B7 才能把某个情景标记为 `proven_by_b5_or_b6`；否则只能说是候选池内最优或需要重优化。
- 交给 A 线的事项：当 B7 标记某情景需要重优化时，由 A 线在该情景下重新生成或调整候选路线。
- 交给 B8 的事项：B7 输出表格行和绘图数据，B8 负责实际图表、路线高亮、动态展示和 GUI 参数交互。

### 当前落地接口

- `mm_final.evaluation.parameter_sensitivity` 提供 `ParameterScenario`、`RouteComponentBreakdown`、`ScenarioEvaluationRecord`、`ScenarioSummary` 和 `SensitivityReport`。
- `default_parameter_scenarios()` 生成第一版单因素扰动代表性情景；`load_parameter_scenarios_json()` 从独立 JSON 配置读取参数情景。
- `analyze_parameter_sensitivity(road_network, candidate_plans=..., scenarios=...)` 是 B7 核心入口，只接已解析的 `RoutePlan` 候选和显式情景列表。
- `analyze_parameter_sensitivity_json_files(...)` 是文件 helper，加载多个 RoutePlan JSON；解析失败会进入 `parse_failed` 情景记录，不污染核心入口。
- `SensitivityReport.to_dict()` 和 `SensitivityReport.to_table_rows()` 分别服务机器读取和 B8/报告层画图；`sensitivity_report_to_markdown()` 生成第 (4) 问人工分析摘要。
- B7 每个情景均使用 B3 final 审计并重算指标，记录候选排名、相对基准 delta、瓶颈路线、路线级停留/行驶分解、重优化提示、可选 B5 最少组数证明摘要和默认 B6 无限人手最短时间摘要。

### 验收标准

- 能生成报告可用的参数表。
- 能解释瓶颈从哪条路线转移到哪条路线。
- 能指出哪些参数变化会触发路线重构需求。

## 9. B8：GUI 与可视化交付

### 目标

负责项目后续 GUI 与可视化交付。B8 的第一版不是单纯静态报告图，而是先建立可复用的 **路线动画时间轴 + 渲染导出核心**，再用轻量 GUI 播放器复用同一套时间轴。B8c 已把 GUI 从“路线动画播放器”升级为 **GUI 全栈问题解决器**，让用户能在同一个入口中选择题目、设置参数、选择算法、触发求解、查看审计诊断、比较方案、播放路线动画并导出结果。

核心体验目标为：根据 `RoutePlan` 在 GUI 中展示多组巡视队的动态推进过程，默认用真实播放 1 秒代表模型时间 1 小时；巡视队用彩色移动点在线路上移动，未经过路线保持黑色或灰色，已经过线段染成对应队伍颜色；用户可拖动进度条查看任意模型时刻，并能导出 GIF 和无声 MP4。无声 MP4 采用 ImageIO 的 `imageio[ffmpeg]` / `imageio-ffmpeg` 路线。

### 输入

- A 线输出的 `RoutePlan` 候选方案。
- B 线复算的 `PlanMetrics` 和 `AuditResult`。
- 路网节点、边权和最短路展开结果。

### 输出

- 路网静态图。
- 路线组高亮图。
- 路线运行过程动画。
- GIF 与无声 MP4 导出。
- 后续轻量 GUI 原型。

### 已拍板决策

1. B8 先走 `shared/viz-dependencies` 增加可视化可选依赖，再走 `b/route-animation-visualization` 实现动画与 GUI；不得直接在 `main` 上实现。
2. B8 拆成 B8a、B8b 和 B8c：B8a 做时间轴模型、任意时刻快照、帧渲染、GIF/视频导出和报告图；B8b 做 GUI 播放器；B8c 将 GUI 升级为全栈问题解决器。
3. B8a 第一版必须覆盖时间轴模型、任意时刻快照、静态帧、GIF、报告图、表格和 README 导出。
4. B8b 第一版必须覆盖加载方案、播放/暂停、拖动进度条、倍速、路线显隐、导出 GIF 和导出无声 MP4；MP4 依赖采用 `imageio[ffmpeg]` / `imageio-ffmpeg`。
5. 纯可视化逻辑放在 `mm_final.visualization`，GUI 入口放在 `apps/`；B8 不把展示逻辑放入 `mm_final.evaluation`。
6. 可视化依赖放入 `viz` optional extra；Matplotlib、Pillow/ImageIO 和 `imageio[ffmpeg]` / `imageio-ffmpeg` 作为第一版基础依赖，Plotly 后置。
7. B8b GUI 框架优先考虑 PySide6/Qt 播放器；Streamlit 不作为第一版播放器首选。
8. GUI 模式按第 (1) 固定组、第 (2) 最少组、第 (3) 足够人手、第 (4) 参数敏感性组织。
9. 第一版只支持导入候选方案；A 线算法运行按钮置灰或标注待接入，不在 B8 内实现搜索。
10. B8c 采用共享 `AlgorithmRunner` / `SolveJob` 契约接入 A 线算法；GUI 不直接绑定 A 线 solver 类、脚本输出或 `print()` 进度。
11. 输入文件为多个 `RoutePlan` JSON，加可选 B5/B6/B7 report JSON；第一版不定义新的 candidate-pool envelope。
12. B8 调用 B3-B7 现有入口重算指标、审计和报告数据；展示层不手写评价指标。
13. 正式展示默认使用 B3 final 审计；candidate 审计只进入调试区，不进入正式报告导出。
14. 参数输入包括 `T`、`t`、`v`、`time_limit`、`k_values`，点击刷新后重算，不做默认实时重算。
15. 参数敏感性情景读取 B7 `ParameterScenario` JSON，也支持 B7 默认情景。
16. B8a 新增 `RouteAnimationTimeline` 或等价结构，提供 `state_at(time_hour)`。
17. 时间轴内部使用模型小时；默认播放比例为真实播放 1 秒代表模型时间 1 小时，并允许导出时覆盖。
18. 动画播放范围默认为 `0` 到方案 `completion_time_hour`，不固定为 24 小时。
19. 队伍沿 B2/B3 复算的 `expanded_node_path` 按边长和速度线性插值移动。
20. 队伍到达乡镇或村后停留对应 `T` 或 `t`；停留时点留在节点，可用等待或脉冲效果提示。
21. 所有队伍 0 时刻位于 `O`；完成各自路线后返回 `O` 并保持可见。
22. 未经过路线初始为黑色或灰色；经过的边段染成对应队伍颜色；当前移动点显示在路线前沿。
23. 支持边内部分染色：队伍走到边中间时，只把已走过的边段染色。
24. 前三队默认使用红、黄、蓝；超过三队时扩展为色盲友好色板。
25. 每队可显示或隐藏；显隐只影响展示，不影响时间轴计算。
26. 进度条显示模型时间小时，可拖动到任意时刻。
27. 播放控制包括播放/暂停、拖动进度条、倍速、重置和导出 GIF。
28. GIF 默认 10 fps，按 `1s = 1h` 的播放比例生成，允许覆盖帧率和比例。
29. GIF 默认时长由模型完成时间决定，例如 18 小时输出约 18 秒。
30. 静态最终路线图由 `state_at(completion_time_hour)` 派生，避免静态图和动画色彩、布局漂移。
31. 坐标布局第一版采用手工转录直线图 layout JSON 作为优先布局，文件为 `data/processed/road_network_layout/original-map-layout.json`；自动布局只能作为缺失 layout 时的兜底。
32. 完整道路网络作为底图，辅助节点弱化显示。
33. depot、乡镇、村、辅助节点使用不同形状或颜色。
34. 边权标签默认关闭，高分辨率导出或选中路线时显示。
35. 指标图包括距离/耗时柱状图、上下界差距图、B7 情景折线或堆叠条。
36. 第 (1) 问展示 3 组路线动画/最终图和距离/耗时均衡图。
37. 第 (2) 问展示每个 `k` 的下界、候选上界、状态表和推荐路线动画/图。
38. 第 (3) 问展示单点一组基线、瓶颈节点、等最短时间候选对比和推荐路线动画。
39. 第 (4) 问展示情景完成时间、瓶颈切换、travel/town/village 占比和重优化提示。
40. 导出格式包括 PNG/SVG 静态图、GIF 动画、无声 MP4、CSV/Markdown/JSON 表格和 README。
41. 输出目录使用 `outputs/b8/<timestamp>/`，保存图、动画、表格和 README。
42. 默认不提交生成图、GIF 或视频；最终报告资产是否入库另行确认。
43. 每次导出生成 `README.md`，记录输入、参数、审计状态、播放比例、帧率、文件清单和复现说明。
44. GUI 状态只保存路径、选中项、播放时刻和显示选项；数学状态来自后端重算，不写回 `RoutePlan`。
45. 无效方案显示 B3/B5/B6/B7 诊断，不因坏候选导致 GUI 崩溃。
46. 当前题面规模下直接重算即可，但需缓存 layout、timeline 和最近帧。
47. 测试覆盖时间轴 `state_at(0/mid/end)`、位置插值、染色边段、停留状态、GIF 非空和首末帧差异；不做脆弱的像素级金图。
48. GUI 文案中文，文件名和结构化字段保持 ASCII。
49. Plotly HTML 交互在 Matplotlib/Qt 动画稳定后再做。
50. 第一版不允许编辑路线，只允许查看、播放和导出。
51. 支持多候选横向比较，默认展示 B3/B5/B6/B7 推荐项。
52. GUI 明确显示候选来源、审计状态、是否强证明、是否候选池最优，避免把启发式候选包装成证明。
53. B8 第一版完成标准为：B8a 能生成 timeline、任意时刻帧、最终图、GIF、指标图、表格和 README；B8b 能加载并拖动播放同一个 timeline。
54. 对不符合当前契约的旧结果采取严格拒绝策略；例如旧辅助节点命名 `U01`、`U02` 或旧拓扑输出不得进入正式审计、报告图或结论，只能在修复后重新导出。
55. 无效候选可以进入 GUI 调试区查看诊断，但报告区、正式比较和推荐导出默认隐藏。
56. B8 导出 README 和机器可读摘要必须记录 Git commit、路网 TSV SHA256、路线契约版本、输入文件路径和 B3 final 审计状态。
57. 动画边几何第一版采用节点间直线段；若报告美化需要贴合手工直线图的折线细节，再维护 edge polyline，不做自动曲线。
58. GUI 或导出入口发现 schema、data、contract、审计模式或版本口径不一致时，必须在顶部摘要或 README 中给出醒目告警，不允许静默修复。
59. 目前不修改 A 线算法代码；若后续发现 A 线源代码仍产生旧契约输出，先向工程师反馈并等待拍板。
60. B8c 目标是把 GUI 从“导入并播放已有方案”升级为“配置问题、运行后端、审计结果、比较方案、动画展示和导出”的全栈问题解决器。
61. B8c 的核心数学、求解、审计、评价和计时逻辑仍属于后端；GUI 只负责参数收集、任务编排、进度呈现、结果选择、图表展示和导出触发。
62. B8c 涉及 `RoutePlan`、候选池、算法 runner、参数情景或结果报告的新公共契约时，必须先走 `shared/...` 分支，不得夹带在 B 线 GUI 分支中。
63. B8c 工作流入口采用按第 (1)-(4) 问分 Tab 的结构，不走第一版向导式入口。
64. B8c 第一版参数自由度只开放 `T`、`t`、`v` 和 `k`；`time_limit`、随机种子、候选数量等工程参数先不作为主界面自由度。
65. B8c 求解执行采用后台任务模式，界面需要显示进度、日志和取消入口，避免长耗时求解阻塞 GUI。
66. B8c 结果对象采用候选方案池，支持多算法、多参数和多次运行结果横向比较。
67. B8c GUI/后端边界采用后端结果展示模式：GUI 不拼装数学指标和结论，只展示后端返回的求解、审计、评价、下界、敏感性和可视化结果。

### 补充已拍板事项

1. **无声 MP4 导出依赖**：选择 ImageIO 的 `imageio[ffmpeg]` / `imageio-ffmpeg` 路线。Matplotlib `FFMpegWriter` + 系统 FFmpeg 和 PyAV 不作为第一版首选。
2. **手工转录直线图布局复原**：选择“直线图底图 + 半手工节点标注 + 归一化 layout JSON”方案。已纳入 `data/processed/road_network_layout/straight-line-layout-source.png` 作为直线图底图源，已纳入 `data/processed/road_network_layout/original-map-layout.json` 作为 B8 渲染器优先读取的节点布局。第一版复原节点空间布局，不手工描摹每条道路的弯曲折线；若后续展示必须沿人工折线移动，再扩展 edge polyline 布局。
3. **旧结果兼容策略**：旧契约或旧路网输出严格拒绝进入正式结果；GUI 调试区可展示错误诊断，但不做 `U01 -> U1` 的正式兼容映射，也不持久改写旧 JSON。
4. **版本与告警策略**：所有 B8 导出物记录 Git commit、路网 TSV SHA256、契约版本和审计状态；GUI 顶部或 README 必须显示 schema/data/contract mismatch 告警。

### 建议实现顺序

1. `shared/viz-dependencies`：新增 `viz` optional extra，至少包含 Matplotlib、Pillow、ImageIO 和 `imageio[ffmpeg]` / `imageio-ffmpeg`。
2. `b/route-animation-visualization` 第一段：新增 `mm_final.visualization` 包，定义 layout、timeline、animation state、route progress、team style 等纯数据结构。
3. 实现 `RouteAnimationTimeline.from_route_plan(...)`，复用 B3 final 和 B2 展开路径，生成每队的行驶段、停留段和完成时间。
4. 实现 `state_at(time_hour)`，返回队伍当前位置、已走线段、当前停留节点、已完成队伍和全局进度。
5. 实现 layout 支持：优先读取 `data/processed/road_network_layout/original-map-layout.json`，自动布局仅作为兜底，并允许后续人工微调坐标；第一版动画边几何采用节点间直线。
6. 实现 Matplotlib 帧渲染：底图、节点样式、未经过线段、已染色线段、当前移动点、时间标注和图例。
7. 实现静态导出：起始帧、任意时刻帧、完成帧、最终路线图和题目所需指标图。
8. 实现 GIF 与无声 MP4 导出：按播放比例和 fps 逐帧调用同一渲染函数，验证首末帧不同、文件非空；MP4 通过 ImageIO/`imageio-ffmpeg` 写入。
9. 实现表格和 README 导出：记录输入路径、参数、审计状态、播放比例、fps、输出文件和复现命令。
10. 新增 B8a 单测：小图手算路线、停留段、插值位置、染色段、layout JSON、PNG/GIF smoke。
11. B8b 第一版 GUI：在 `apps/` 中创建播放器入口，加载 RoutePlan 和 layout，复用 timeline，提供播放/暂停、进度条、倍速、路线显隐、GIF 导出和无声 MP4 导出。
12. B8b smoke 测试：至少覆盖 GUI 入口可导入、timeline 加载不崩溃、拖动进度条时图像更新、路线显隐状态可读；交互细节以手工验收为主。

### 已落地实现切片

- `mm_final.visualization.layout`：读取手工转录直线图 layout JSON，并在缺失 layout 时用稳定自动布局兜底。
- `mm_final.visualization.timeline`：根据 `RoutePlan`、当前 `RoadNetwork` 和 B2/B3 参数生成 `RouteAnimationTimeline`，支持 `state_at(time_hour)` 查询队伍移动、停留、完成状态和已染色边段。
- `mm_final.visualization.rendering`：延迟导入 Matplotlib 和 ImageIO，支持 PNG、GIF 和无声 MP4 导出；第一版边几何为节点间直线。
- `mm_final.visualization.exports`：提供严格 B3 final 门禁、版本锁定信息、`timeline-summary.json`、`route-summary.csv` 和 README 导出；旧契约结果默认拒绝进入正式导出。
- `apps/gui/route_animation_player.py`：提供无 GUI 重依赖的路线动画导出入口。
- `apps/gui/route_animation_gui.py`：提供 B8c PySide6/Qt GUI 全栈问题解决器，复用同一套 timeline 和 renderer，并通过共享 `AlgorithmRunner` / `SolveJob` 契约支持第 (1)-(3) 问后台求解、候选方案池、第 (4) 问参数敏感性分析、加载方案、播放/暂停、拖动进度条、倍速、路线显隐、GIF/无声 MP4 导出和 B3 final 诊断展示。

### 潜在交互需求

- 选择第 (1)-(4) 问，切换固定组、最少组、人员足够和参数敏感性四类 Tab 工作流。
- 使用滑块或输入框调节 `T`、`t`、`v`、`k`；`time_limit`、随机种子和候选数量等工程参数后置到高级设置或后续版本。
- 选择已接入的 A 线算法或后端分析入口，触发求解、审计和评价。
- 对比多个候选方案，查看推荐项、上下界差距、瓶颈路线和重优化提示。
- 切换路线组显示/隐藏，悬停或点击节点查看节点类型、停留时间和所属路线。
- 导出当前图像、GIF、无声 MP4、表格、报告摘要和可复现结果包。

### 验收标准

- 生成的图能直接用于书面报告。
- 动态展示能直观看到每组路线的推进过程。
- 第一阶段至少支持 GIF 导出。
- GUI 不直接修改后端数学状态，只通过契约输入和指标输出交互。

## 10. 与 A 线的握手节奏

### H1：契约测试先行

B 线先提供最小合法方案和若干非法方案夹具。A 线第一个构造器输出后，必须能通过 B 线契约读取和审计。

### H2：距离与路径复核

A 线提供最短路闭包或路径查询结果时，B 线抽样复核若干节点对，确认距离单位、路径展开和辅助节点处理一致。

### H3：候选方案池审计

A 线每次提交候选方案池，B 线返回：

- 合法性错误；
- 复算指标；
- 瓶颈路线；
- 是否满足时间上限；
- 若不可行，是“候选差”还是“下界已排除”。

### H4：最终结果合成

B 线最终交付不是单独一组数值，而是：

- 每个问题的审计结论；
- 对应路线方案的合法性证明；
- 下界或不可能性解释；
- 参数敏感性结论。

## 11. 推荐开工顺序

1. 创建 `b/track-b-bootstrap` 分支。
2. 编写契约读取测试和手工 `RoutePlan` 夹具。
3. 实现节点分类与必访点全集测试。
4. 实现方案评价器。
5. 实现可行性审计器。
6. 实现基础下界计算。
7. 实现 24 小时最少组数判定框架。
8. 实现人员足够时最短完成时间分析。
9. 实现参数敏感性分析表。
10. 在结果契约稳定后推进 GUI 与可视化。

每一步都应先有测试或手工夹具，再写实现。若发现契约字段不足，暂停 B 线功能开发，转入 `shared/...` 分支处理契约变更。

## 12. 风险清单

- **格式漂移**：A/B 各自维护不同方案结构。应通过契约测试阻断。
- **单位漂移**：公里、小时、速度单位混用。应在字段名中保留单位。
- **辅助节点误计停留**：`U1`-`U6` 只能通行，不能停留。
- **过早宣称不可能**：候选方案不可行不等于组数不可能，必须有下界支持。
- **下界过弱**：弱下界只能用于筛查，不能支撑强结论。
- **参数敏感性只给图不解释**：必须说明为什么路线结构或瓶颈发生变化。
- **共享契约夹带在 B 分支中**：涉及契约变更时必须走 `shared/...`。
- **GUI 污染后端**：GUI 只能展示和触发求解，不能承载核心数学逻辑。
