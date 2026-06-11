# 分阶段实施计划

本文档记录项目的实施计划。当前确认采用双线并行协作：

- **A 线：路线构造与空间优化线**，负责生成候选巡视路线。
- **B 线：耗时审计、下界证明与参数分析线**，负责判断方案是否合法、是否满足约束，并解释组数与参数变化。

两条线的关系不是“后端生产、展示消费”，而是“构造者与审计者并行推进”。A 线可以在 B 线评价器尚未完备时先用简单指标迭代路线；B 线可以在 A 线算法尚未完成时用手工方案、小图方案和占位方案推进审计、下界和敏感性分析。

---

## 0. 项目目标理解

本项目要在题面给出的县域道路网络上，为从节点 `O` 出发并返回 `O` 的多组巡视任务设计路线。必须巡视节点包括乡（镇）节点 `A`–`R` 与村节点 `1`–`35`，辅助道路节点 `U01`–`U05` 只承担道路连接作用。

四个原始问题可统一抽象为带节点服务时间的多路线巡视问题：

- 第 (1) 问：固定 3 组，设计总路程短且各组尽可能均衡的路线；本项目初期将“均衡”优先解释为各组路线距离接近。
- 第 (2) 问：给定 `T=2h`、`t=1h`、`v=35km/h` 与 24 小时上限，寻找最少组数及对应最佳路线。
- 第 (3) 问：巡视人员足够多时，寻找理论最短完成时间与对应路线。
- 第 (4) 问：固定组数时，分析 `T`、`t`、`v` 改变对最佳路线的影响。

`docs/theories.md` 提供欧拉图、奇偶点与扫雪问题思路，可作为建模类比：它强调图结构、重复路程、连通分区与均衡目标。但本项目并非必须遍历所有边，而是必须访问所有乡镇村节点，因此后续实现应以“必访节点 + 最短路闭合路线 + 多组划分”为主，欧拉思想主要用于解释图论背景和扩展讨论。

## 1. 共同基础与对接原则

### 1.1 统一对接格式是最高优先级

A/B 双线最大的风险是“各自都能跑，但方案格式、单位、节点语义、指标口径不一致”。因此，所有路线生成、审计、实验和展示都必须先服从统一对接契约，再讨论具体算法优劣。

对接契约详见 `docs/contracts/route-plan-contract.md`。后续实现时应把该契约转化为测试夹具和数据模型：

- A 线输出必须符合契约，不能输出临时拼接字符串作为正式结果。
- B 线输入只接受契约格式，不能为某个算法特判解析。
- 任一字段口径变化，必须先更新契约文档、测试和改动记录。
- 契约字段命名、单位和节点语义优先于个人实现习惯。

### 1.2 双线共享但不重复的基础能力

两条线都需要使用以下公共能力，但职责不同：

- 路网读取：统一从 `data/raw/road_network.tsv` 读取。
- 节点分类：统一识别乡镇、村、辅助道路节点和县政府节点。
- 最短路查询：提供原始道路网络上任意节点之间的最短距离与路径。
- 路线方案格式：统一用 `RoutePlan`、`Route`、`RouteMetrics`、`AuditResult` 等概念表达。

A 线使用这些能力来生成方案；B 线使用这些能力来审计方案。任何共享能力都应有测试，避免两条线各自复制一套规则。

### 1.2.1 统一路网标准

`shared/road-network-core` 中由 B 线推进并落地的路网标准，是 A/B 两线后续共同遵守的最终统一标准。该标准包括：

- 节点语义：`O` 是县政府所在地和 depot，不属于乡镇；`A`–`R` 中除 `O` 外的大写字母是乡镇；`1`–`35` 是村；`U01`–`U05` 是辅助道路节点。
- 节点分类：统一使用 `mm_final.network.nodes.NodeType` 和 `classify_node`。
- 路网读取：统一从 `data/raw/road_network.tsv` 读取，测试和扩展场景可传入自定义 TSV 路径。
- 图结构：统一使用 `mm_final.network.RoadNetwork` 包装无向加权图；外部如需 NetworkX 图，只通过 `to_networkx()` 获取副本。
- 数据校验：正式 TSV 必须满足表头、三列、正边权、无未知节点、无重复无向边、所有必访节点存在、整图连通等规则。

A 线工程师开工前必须先确认本节、`docs/contracts/route-plan-contract.md` 和 `docs/detailed-plan-for-track-A.md`。A 线不得重新定义节点集合、辅助节点语义或路网读取规则；如果发现标准不足，必须先走 `shared/...` 分支变更公共底基。

### 1.3 语言选择

语言已确认尽可能只使用 Python。理由是本项目图规模较小，Python 更适合快速完成图算法、实验调度、可视化、测试和报告支撑，也更便于两线并行时共享契约与测试夹具。

保留后期引入 C++ 的可能，但只在以下情况出现时评估：

- Python 实现已被计时系统定位为明确性能瓶颈；
- 优化算法扩展到大量随机搜索、元启发式或大规模实例；
- C++ 加速核心可以保持 A/B 对接契约不变，只作为内部实现细节存在。

默认约束：C++ 不得绕过 `docs/contracts/route-plan-contract.md`，不得改变 Python 侧公开数据结构和测试口径。

### 1.4 Git 双线协作规则

A/B 两线并行开发时，采用“稳定 `main` + 短生命周期功能分支”的方式。A 线使用 `a/...` 分支，B 线使用 `b/...` 分支；涉及路线方案契约、公共数据结构、公共测试夹具的改动使用 `shared/...` 分支。

关键规则：

- `shared/...` 分支优先合并到 `main`，A/B 两线再基于最新 `main` 继续开发。
- 契约变更不得夹带在 A/B 功能分支中。
- 每次合并前必须同步最新 `main`，解决冲突并运行当前阶段已有测试。
- 合并冲突时，公共契约和测试口径优先，A/B 算法实现服从契约。

详细规范见 `docs/git-workflow.md`。

### 1.5 环境与依赖策略

项目采用 `pyproject.toml` 作为 Python 项目元数据、依赖声明和工具配置入口，采用 uv 管理虚拟环境同步和锁文件。核心依赖优先考虑 `networkx`、`numpy`、`scipy`；可视化采用 Matplotlib + NetworkX + Pillow/ImageIO + Plotly；GUI 第一阶段不启动，后续轻量展示优先评估 Streamlit；动态展示第一阶段优先支持静态图 + GIF。

版本库提交 `pyproject.toml`、`uv.lock` 和环境创建说明，不提交 `.venv`。其他开发者拉取仓库后应通过 uv 基于锁文件重建本机虚拟环境，从而获得一致的依赖版本；`.venv` 本体具有机器相关性，不作为可复现来源。

环境和依赖变更属于共享基础，应走 `shared/...` 分支。详细策略与待确认问题见 `docs/environment-and-dependencies.md`。

## 2. A 线：路线构造与空间优化线

A 线主责是“给出怎么走”。它不负责证明某个组数是否最少，也不负责解释参数敏感性；它负责在给定组数、给定必访点集合、给定优化目标时，生成尽可能好的闭合巡视路线。

### 阶段 A1：路网空间结构理解

目标：

- 建立道路网络、节点类型、边权与必访点集合。
- 计算或查询原始路网上的最短路。
- 将必访节点之间的距离闭包作为路线构造基础。

完成标准：

- 基于 `mm_final.network` 使用统一的 `RoadNetwork` 和 `NodeType`，不得另写一套路网读取或节点分类。
- 能从 `data/raw/road_network.tsv` 获取已校验的无向加权图。
- 能区分 `O`、乡镇节点、村节点和辅助道路节点，并遵守 `O` 不属于乡镇的统一语义。
- 能查询任意两点的最短距离与实际经过节点序列。
- 输出结果使用公里作为距离单位。

### 阶段 A2：单路线构造器

目标：

- 给定一组必访点，生成一条从 `O` 出发并回到 `O` 的闭合巡视路线。
- 先实现可解释的基线方法，再实现局部改进。

建议方法：

- `Clarke-Wright savings` 节约算法；
- 最便宜插入；
- 路线内 2-opt；
- 多起点重启。

完成标准：

- 单路线覆盖输入中的全部必访点。
- 单路线不把辅助道路节点当作必须停留点。
- 单路线能展开为原始路网上的实际通行节点序列。
- 输出符合 `RoutePlan` 契约，即使只有一条路线也必须走统一格式。

### 阶段 A3：固定 3 组路线优化

目标：

- 主攻第 (1) 问。
- 将所有必访点划分给 3 条路线，并分别构造闭合路线。
- 优化目标建议采用“总路程优先，均衡性次优先”的词典序目标。

建议方法：

- 基于方位/距离的初始分区；
- k-medoids 或类似聚类的初始分组；
- 组间节点交换；
- relocate 节点迁移；
- 路线内局部搜索；
- 多候选方案保留。

完成标准：

- 输出 3 条从 `O` 出发并返回 `O` 的路线。
- 所有乡镇和村节点被覆盖且只分配给一组。
- 输出总路程、各组路程和基础均衡指标；初期基础均衡指标至少包括路线距离极差，后续可在报告层补充标准差、偏离平均值等统计解释。
- 方案交给 B 线审计时不需要额外解释字段含义。

### 阶段 A4：任意组数路线生成

目标：

- 让构造器支持 `k=1,2,3,...`。
- 为第 (2)(3) 问提供候选方案池。

完成标准：

- 给定组数 `k` 后，能输出 `k` 条闭合路线。
- 能处理空路线禁用或空路线剔除策略。
- 能提供多套候选方案，供 B 线比较可行性和瓶颈。

### 阶段 A5：路线改进与方案池管理

目标：

- 提升路线质量，避免单一启发式误导结论。
- 将不同策略生成的候选方案统一放入方案池。

建议方法：

- 随机重启；
- 模拟退火；
- 组间节点迁移、交换、二换一；
- 路线内 2-opt/3-opt；
- 按总路程、最大路程、均衡性保留非支配方案。

### A 线推荐优先实现的五种算法

综合实现难度、可解释性和对本题的适配度，A 线优先实现以下五种经典算法即可形成足够完整的求解闭环：

1. `Clarke-Wright savings` 节约算法：多路线初解构造。
2. `k-medoids / cluster-first route-second`：固定组数下的图距离分组。
3. `2-opt`：路线内部访问顺序改进。
4. `relocate` 节点迁移：跨路线负载和均衡调整。
5. 模拟退火：组合邻域操作，跳出局部最优。

为让 A 线自然接入这些方法，B2 阶段应顺手补齐共享评分底座：最短路闭包、`CandidateSolution`、`ObjectiveSpec`、路线距离/耗时快速计算、分组器接口、组内路线构造器接口、`2-opt`/`relocate`/`swap` 等邻域操作、空路线处理策略、`CandidateSolution -> RoutePlan` 导出器和方案池。共享评分核心服务于 A 线高频优化，B 线仍保留权威审计、下界证明和报告解释职责。

B2 不实现五种经典算法主体，只提供稳定接口和基础操作；A 线负责具体搜索策略、算法参数、迭代停止条件和候选方案生成。

完成标准：

- 对同一组数能输出多个候选 `RoutePlan`。
- 每个候选方案都有算法来源、随机种子和运行耗时记录。
- 候选方案可直接交给 B 线审计与排序。

## 3. B 线：耗时审计、下界证明与参数分析线

B 线主责是“判断方案是否成立、为什么成立或不成立”。它不等待 A 线最终算法完成，而是先用手工方案、小图方案和占位方案建立评价、审计、下界与敏感性分析能力。

### 阶段 B0：契约落地与测试夹具

目标：

- 将 `RoutePlan`、`Route`、`RouteMetrics`、`PlanMetrics`、`AuditResult` 等对接契约落地为可读写的数据模型和测试夹具。
- 保证 A/B 两线在正式算法前先能读写同一种路线方案结构。

完成标准：

- 能读取最小 schema smoke 方案和完整覆盖 smoke 方案。
- 缺字段、错误 `schema_version`、`O` 或辅助节点误入 `required_visit_order` 等核心契约错误能被测试捕获。
- 契约模型和共享夹具走 `shared/...` 分支，不能夹带在 A/B 私有功能分支中。

### 阶段 B1：路网语义与节点分类复核

目标：

- 建立统一的道路网络读取、节点分类、边权校验和连通性校验能力。
- 确保停留时间、覆盖检查和最短路计算共享同一套路网语义。

完成标准：

- 统一从 `data/raw/road_network.tsv` 读取正式路网。
- 使用 `mm_final.network` 识别 `O`、乡镇节点、村节点和辅助道路节点。
- 正式 TSV 通过表头、三列、正边权、无未知节点、无重复无向边、必访节点存在、整图连通等校验。

### 阶段 B2：方案评价器

目标：

- 对任意符合契约的 `RoutePlan` 计算路程和耗时。
- 明确所有单位和停留时间口径。
- 复用共享快速评分底座，但不提前给出最终合法性结论。

评价内容：

- 单条路线行驶距离；
- 单条路线行驶时间；
- 乡镇停留时间；
- 村停留时间；
- 单条路线总耗时；
- 全方案完成时间，即最长路线耗时；
- 总路程与均衡性指标；B 线初期以距离极差和耗时极差为核心复核指标。

完成标准：

- 输入手工构造的路线方案也能评价。
- `T`、`t`、`v` 可参数化。
- 辅助道路节点不产生停留时间。
- 输出 `EvaluationResult`，包含复算指标、覆盖摘要、瓶颈路线、距离均衡摘要和结构化诊断。
- B2 只负责复算和诊断；最终合法性判定留给 B3。

### 阶段 B3：可行性审计器

目标：

- 独立判断路线方案是否合法。
- 主动发现 A 线方案中的遗漏、重复和格式错误。
- 复用 B0 契约读取结果和 B2 评价结果，形成可用于结果讨论的 `AuditResult`。

审计内容：

- 每条路线是否从 `O` 出发并回到 `O`；
- 所有乡镇节点和村节点是否全部覆盖；
- 必访点是否重复分配；
- 辅助道路节点是否被错误计入停留；
- 展开路径是否与原始道路网络连通；
- 路线距离是否与最短路展开结果一致；
- 字段、单位、版本是否符合契约。

已确认口径：

- B3 本体走 `b/route-plan-auditor` 分支；只有契约字段、共享夹具或公共审计口径变化才切到 `shared/...`。
- 审计器放在 `mm_final.evaluation.route_plan_auditor`，入口建议为 `audit_route_plan(plan, road_network, parameters=None, mode=...) -> AuditResult`。
- B3 第一版支持 `candidate` 与 `final` 两种模式；`final` 是严格终审，`candidate` 用于 A 线中间候选方案诊断。
- B3 核心入口只接收已解析的 `RoutePlan`；无法解析的 JSON 方案由 helper 转换为 `schema_valid = false` 的文件级审计结果。
- `candidate` 模式中 schema 错误和展开路径坏边仍为 error，覆盖遗漏、重复、空路线和 metrics 不一致降级为 warning。
- 空路线、遗漏必访点、重复必访点、`route_id` 重复、辅助节点误入必访顺序、展开路径坏边和已提供指标不一致等问题，在 `final` 模式下均应给出明确错误或无效分类。
- 24 小时上限不属于 B3 路线合法性；超时结论留给 B5 最少组数判定流程使用。
- B3 第一版不修改 `AuditResult` 新增机器可读 `mode` 字段；如 GUI 或报告生成器后续需要自动区分 `candidate` 与 `final`，再走 `shared/...` 评估契约变更。
- B3 同时生成 Markdown 审计摘要，服务人工分析和报告草稿；Markdown 只作为结构化审计结果的派生视图。

完成标准：

- 不合法方案能给出具体错误列表。
- 合法方案能给出 `AuditResult`。
- 审计器不依赖 A 线具体算法。
- 当前已落地 `audit_route_plan()`、`audit_validation_result()`、`audit_route_plan_json()` 和 `audit_result_to_markdown()`，可对手工或 A 线候选 `RoutePlan` 做结构化审计和 Markdown 摘要。

### 阶段 B4：组数下界与不可能性分析

目标：

- 主攻第 (2)(3) 问中的“至少”和“理论极限”。
- 区分“当前候选方案不好”和“数学上不可能”。

建议下界：

- 总停留时间容量下界；
- 单点最短往返时间下界；
- 若干区域或节点集合的负载下界；
- 固定组数下最大可服务量下界；
- 由 `O` 到远端节点的往返距离造成的瓶颈下界。

已确认口径：

- B4 本体走 `b/lower-bound-analysis` 分支，模块放在 `mm_final.evaluation.lower_bounds`。
- B4 输出结构化 `LowerBoundReport` 和 Markdown 摘要，不修改 `RoutePlan`、`AuditResult` 或 `PlanMetrics` 契约。
- B4 第一版只做可解释下界：总停留时间容量下界、单点往返下界和简单集合负载下界。
- B4 不读取 A 线候选方案池，不依赖 B3 审计结果，不直接输出最少组数或第 (3) 问最终结论。
- 不可能性状态使用 `lower_bound_impossible`、`not_excluded`、`insufficient_evidence`；只有严格数学成立的下界才能用于强排除。
- 每个下界条目需要标注强弱类型，例如 `strict/provable`、`screening_only` 或 `heuristic`。

已落地接口：

- 核心入口为 `compute_lower_bound_report(road_network, k_values=..., parameters=...)`，并提供 `default_k_values()` 生成默认扫描范围。
- 输出数据类包括 `LowerBoundParameters`、`LowerBoundEntry`、`GroupLowerBound` 和 `LowerBoundReport`，其中 `LowerBoundReport.to_dict()` 用于 B5/B6 机器读取。
- `lower_bound_report_to_markdown()` 生成面向人工分析和报告草稿的 Markdown 摘要。
- `GroupLowerBound.status` 只由 `strict/provable` 证据决定；`screening_only` 证据只能进入说明，不能直接排除组数。

完成标准：

- 能说明某些组数为什么不可能满足 24 小时。
- 能为人员足够时的最短完成时间给出理论下界。
- 下界计算可被测试复核。

### 阶段 B5：24 小时最少组数判定

目标：

- 主攻第 (2) 问。
- 从 `k=1` 开始，结合下界和 A 线候选方案判断 24 小时可行性。

已确认口径：

- B5 本体走 `b/minimum-group-decision` 分支，模块放在 `mm_final.evaluation.minimum_group_count`。
- B5 输出 `MinimumGroupReport`、`GroupDecisionRecord` 和 `CandidateDecisionRecord` 或等价结构，并提供 `to_dict()` 与 Markdown 摘要。
- B5 第一版不修改 `RoutePlan`、`AuditResult` 或 B4 下界结构；候选池以按 `k` 归组的 `RoutePlan` 集合作为核心输入。
- 第一版不定义新的 candidate-pool JSON envelope；它不是必做项，可以长期不做。只有当多算法、多目录、跨进程或 GUI 批量交换需要统一元数据时，才走 `shared/...` 讨论候选池文件契约。
- B5 可接收已有 `LowerBoundReport`，也可内部调用 B4；`lower_bound_impossible` 直接强排除，`not_excluded` 和 `insufficient_evidence` 继续审计候选池。
- B5 只使用 B3 `final` 审计作为正式结论门禁；候选必须四类 valid 全真、复算指标存在、组数等于当前 `k` 且 24 小时内完成，才能形成 feasible upper bound。
- 每个 `k` 的状态使用 `lower_bound_impossible`、`candidate_feasible`、`candidate_not_found`、`candidate_invalid`、`insufficient_evidence`；总报告结论等级使用 `proven_minimum`、`incumbent_minimum` 或 `no_feasible_candidate`。
- 第一版不使用 B2/共享 `score_candidate()` 预筛；候选池很大时可加可选预筛层，但预筛只排序、分批或截取进入终审的候选，不能替代 B3 final 或形成最少组数结论。

已落地接口：

- 核心入口为 `decide_minimum_group_count(road_network, k_values=..., candidate_plans_by_k=..., parameters=...)`，只接已解析的 `RoutePlan`。
- 文件入口为 `decide_minimum_group_count_json_files(...)`，按 `k` 加载多个 RoutePlan JSON，并把解析失败文件转成 invalid 候选记录。
- 输出数据类包括 `MinimumGroupParameters`、`CandidateDecisionRecord`、`GroupDecisionRecord` 和 `MinimumGroupReport`，其中 `MinimumGroupReport.to_dict()` 用于报告层和 B8 机器读取。
- `minimum_group_report_to_markdown()` 生成第 (2) 问人工分析和报告草稿所需的 Markdown 摘要。

完成标准：

- 对每个 `k` 输出：理论下界、最佳候选方案耗时、是否可行、失败原因。
- 当某个 `k` 可行时，能说明更小组数为何不采用。
- 输出最少组数下的推荐路线。
- 继承 B4 留后的候选方案池对比、上下界差距计算和最少组数状态合成；不得把 B4 的筛查性弱下界直接当作强排除结论。

### 阶段 B6：人员足够时的最短完成时间

目标：

- 主攻第 (3) 问。
- 分析无限人手时的完成时间极限，而不是简单假设每个点一组。

分析重点：

- 单点独立巡视的往返时间与停留时间；
- 近邻节点合并巡视是否降低最大耗时；
- 最远节点或高停留负载节点是否形成瓶颈；
- 最短完成时间下需要多少组及其路线结构。

已确认口径：

- B6 本体走 `b/unlimited-personnel-time` 分支，模块放在 `mm_final.evaluation.unlimited_personnel_time`。
- B6 输出 `UnlimitedPersonnelReport` 和 `ShortestTimeCandidateRecord` 或等价结构，并提供 `to_dict()` 与 Markdown 摘要。
- B6 第一版不修改 `RoutePlan`、`AuditResult` 或 B4 下界结构；B6 结论是方案外证明与推荐材料。
- B6 自动生成单点一组 `singleton_certificate` 基线，用于证明上界等于 B4 的 `unlimited_personnel_lower_bound_hour`。
- B6 核心入口接收不按 `k` 归组的 `RoutePlan` 候选集合；文件 helper 加载多个 RoutePlan JSON，不定义新的候选池 envelope。
- 第 (3) 问不以 24 小时为合法性门禁；候选进入推荐只要求 B3 final 四类 valid 全真且复算指标存在。
- 最短时间结论等级使用 `proven_shortest_time`、`incumbent_shortest_time` 或 `no_valid_candidate`；完成时间在下界容差内的候选视为等最短时间候选。
- 推荐路线先筛等最短时间候选，再按组数、总路程、耗时极差、路程极差和 `plan_id` 排序；单点一组基线可兜底，但若有更少组的等最短时间候选应优先推荐候选。
- B6 不搜索近邻合并，只审计 A 线或手工合并候选并记录 secondary objective 改进空间；不把 B5 包装成 B6。

已落地接口：

- 核心入口为 `analyze_unlimited_personnel_time(road_network, candidate_plans=..., parameters=...)`，只接已解析的 `RoutePlan`。
- 文件入口为 `analyze_unlimited_personnel_time_json_files(...)`，加载多个 RoutePlan JSON，并把解析失败文件转成 `parse_failed` 候选记录。
- `build_singleton_certificate_plan(parameters=...)` 生成单点一组 `RoutePlan`，供第 (3) 问证明基线、报告附件和后续可视化复用。
- 输出数据类包括 `UnlimitedPersonnelParameters`、`ShortestTimeCandidateRecord` 和 `UnlimitedPersonnelReport`，其中 `UnlimitedPersonnelReport.to_dict()` 用于报告层、B7 和 B8 机器读取。
- `unlimited_personnel_report_to_markdown()` 生成第 (3) 问人工分析和报告草稿所需的 Markdown 摘要。

完成标准：

- 给出最短完成时间候选值。
- 给出达到该时间的路线方案。
- 给出下界解释，说明该值为什么可信。
- 继承 B4 留后的无限人手完成时间下界，并结合 A 线或手工候选路线形成上下界差距；只有上下界合拢时才宣称强最优结论。

### 阶段 B7：参数敏感性分析

目标：

- 主攻第 (4) 问。
- 固定组数时，讨论 `T`、`t`、`v` 的变化对最佳路线的影响。
- 第一版做成参数情景审计与敏感性报告层：对给定代表性 `RoutePlan` 候选在不同参数情景下统一重算、B3 final 审计、排序和解释，不承担 A 线路线重优化职责。

分析内容：

- `T` 增大时，乡镇节点对瓶颈路线的影响；
- `t` 增大时，村节点数量对分组负载的影响；
- `v` 改变时，行驶距离和停留时间在目标函数中的权重变化；
- 路线合并、拆分、换点的临界条件；
- 固定 3 组与其他组数下的对比。
- 继承 B6 留后的参数化最短时间分析能力，扫描 `T`、`t`、`v` 对第 (3) 问最短完成时间值、瓶颈节点和单点一组基线结构的影响。

已确认口径：

- B7 本体走 `b/parameter-sensitivity-analysis` 分支，模块放在 `mm_final.evaluation.parameter_sensitivity`。
- B7 输出 `SensitivityReport`、`ParameterScenario` 和 `ScenarioEvaluationRecord` 或等价结构，并提供 `to_dict()`、Markdown 摘要和表格行 helper。
- B7 第一版不修改 `RoutePlan`、`AuditResult` 或 B4/B5/B6 既有结构；参数敏感性结论是方案外分析材料。
- B7 核心输入为 `candidate_plans: Iterable[RoutePlan]` 与显式 `ParameterScenario` 列表；文件 helper 可加载多个 RoutePlan JSON 和情景配置，但不定义新的 sensitivity-pool JSON envelope。
- 默认基准参数采用 `T=2h`、`t=1h`、`v=35km/h`；默认代表性情景以单因素扰动为主，例如 `T={1.5,2.0,2.5}`、`t={0.5,1.0,1.5}`、`v={25,35,45}`，第一版不做三维密集全扫。
- B7 每个情景都按显式参数调用 B3 final 终审并重算指标；24 小时上限默认只作为展示字段，不作为敏感性比较的硬门槛。
- 每个情景下的推荐候选先按完成时间排序，再按总路程、耗时极差、路程极差和 `plan_id` 排序。
- B7 记录相对基准的完成时间变化、总路程变化、瓶颈路线变化、停留/行驶占比变化和候选排名变化。
- B7 的路线结构变化判断只作为 `screening_only` 重优化提示，不能直接作为全局最优或不可能性的数学证明。
- 情景结论应区分候选池内最优、需要重优化、由 B5/B6 证明和无合法候选等状态，避免把启发式候选值写成强最优结论。
- B7 可选复用 B5 重新判断参数情景下的 24 小时最少组数，可选复用 B6 生成无限人手最短完成时间摘要；这些证明摘要不替代 B7 的固定候选敏感性分析。
- B7 输出可画图的表格数据，实际图表、路线高亮、动态展示和 GUI 参数交互留给 B8。

已落地接口：

- `mm_final.evaluation.parameter_sensitivity` 提供参数情景、情景候选记录、情景摘要和敏感性报告结构。
- `analyze_parameter_sensitivity()` 对已解析 `RoutePlan` 候选做核心情景分析；`analyze_parameter_sensitivity_json_files()` 处理文件级候选和解析失败记录。
- `default_parameter_scenarios()` 和 `load_parameter_scenarios_json()` 分别支持默认代表性情景和独立情景配置。
- `SensitivityReport.to_dict()`、`SensitivityReport.to_table_rows()` 和 `sensitivity_report_to_markdown()` 分别服务机器读取、B8 图表数据和人工报告草稿。

完成标准：

- 形成参数网格或若干代表性场景。
- 输出瓶颈路线变化、完成时间变化和路线结构变化。
- 形成报告可直接引用的结论和图表说明。
- 若比较不同参数下的候选路线，继续使用 B3 final 审计和 B6 上下界差距口径，避免把启发式候选值写成强最优结论。

### 阶段 B8：GUI 与可视化交付

目标：

- 在结果契约和评价审计口径稳定后，负责报告图、路线过程动态展示、GIF/无声视频导出和后续轻量 GUI。
- GUI 只负责参数输入、求解触发、路线展示、图表展示和结果导出，不承载核心数学逻辑。

完成标准：

- 能生成书面报告可直接使用的路线图和指标图。
- 动态展示能直观看到每组路线推进过程。
- 第一阶段至少支持静态图和 GIF 导出；后续再评估交互式 Plotly 或 Streamlit GUI。

## 4. A/B 握手点

### 握手点 H1：路线方案契约

时间：A2 和 B0/B1 开始前。

内容：

- 共同确认 `RoutePlan`、`Route`、`RouteMetrics`、`AuditResult` 字段。
- 建立最小样例方案。
- 建立契约测试：A 输出的样例能被 B 读取，B 的审计错误能被 A 理解。

### 握手点 H2：最短路闭包

时间：A1 完成后，B2 使用前。

内容：

- 统一最短路距离、实际路径和单位。
- 明确辅助道路节点可以出现在展开路径中，但不能作为必访停留点。
- 对若干节点对进行人工复核，作为回归测试。

### 握手点 H3：固定 3 组候选方案

时间：A3 形成第一批候选方案后。

内容：

- A 提交多套 3 组方案。
- B 返回合法性、耗时、均衡性和瓶颈说明。
- 双方根据审计结果决定下一轮改进方向。

### 握手点 H4：任意组数方案池

时间：A4/B5 对接时。

内容：

- A 对每个 `k` 提供候选方案池。
- B 对每个 `k` 给出理论下界、候选最优耗时和可行性判断。
- 若候选方案不可行但下界未排除该组数，A 继续搜索；若下界已排除，A 不再为该组数投入优化。

### 握手点 H5：最终结果合成

时间：第 (1)–(4) 问收束时。

内容：

- A 线提供路线结构和路线生成方法说明。
- B 线提供约束审计、下界证明、参数敏感性解释。
- 最终报告同时引用路线方案和审计结果，避免只有路线没有可信性说明，或只有理论没有可执行路线。

## 5. 原始问题主责划分

- 第 (1) 问：A 线主责，B 线负责合法性审计、均衡指标复核和结果解释。
- 第 (2) 问：B 线主责最少组数判定，A 线负责为候选组数生成路线方案。
- 第 (3) 问：B 线主责理论最短完成时间和下界解释，A 线负责构造达到该时间的路线。
- 第 (4) 问：B 线主责参数敏感性分析，A 线负责在代表性参数下重新生成或调整路线。

## 6. 附加交付任务分工

- GUI 与可视化：B 线工程师负责，重点包括报告图、路线过程动态展示、GIF/无声视频导出和后续轻量 GUI。
- 上台展示：A 线工程师负责，重点包括汇报结构、展示材料组织和现场讲解。
- 书面报告：两人共同完成，各自负责自己工作内容对应的建模、算法、审计、可视化和结论部分。

## 7. 当前待确认问题

1. 优化目标优先级：第 (1) 问建议采用“总路程优先，均衡性作为次级目标或约束”的词典序目标。
2. 契约落地方式：建议在正式编码前先写 `RoutePlan` 契约测试，再实现 A/B 两侧功能。
3. Python 版本：等待 A 线工程师确认。
