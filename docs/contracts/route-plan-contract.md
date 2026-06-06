# 路线方案对接契约

本文档定义 A 线与 B 线之间的统一对接格式。A 线负责生成路线方案，B 线负责评价、审计、下界分析和参数敏感性分析。双方必须通过本文档约定的结构交换数据。

---

## 1. 契约原则

1. **先契约，后算法**：任何路线构造方法都必须输出统一结构；任何审计方法都必须只依赖统一结构。
2. **单位显式**：距离统一为 `km`，时间统一为 `hour`，速度统一为 `km_per_hour`。
3. **节点语义固定**：`O` 是县政府所在地；`A`–`R` 中除 `O` 外的大写字母是乡镇；`1`–`35` 是村；`U01`–`U05` 是辅助道路节点。
4. **必访点与通行点分离**：路线的必访顺序只包含乡镇和村；展开路径可以包含辅助道路节点。
5. **审计可复现**：每个方案必须保留算法名、参数、随机种子和契约版本。

## 1.1 必访顺序与实际通行路径

本契约中必须严格区分两个概念：

- `required_visit_order`：必访停留节点顺序，只表达该组人员真正需要巡视、停留和服务的乡镇或村节点。
- `expanded_node_path`：原始道路网络上的实际通行节点序列，表达车辆真实经过的路径。

因此，一条路线在现实中必须从 `O` 出发并最终回到 `O`，但 `O` 不写入 `required_visit_order`。`O` 的出发和返回语义由 `depot = "O"` 以及 `expanded_node_path` 的首尾节点表达。

辅助道路节点 `U01`–`U05` 只能出现在 `expanded_node_path` 中，不能出现在 `required_visit_order` 中，因为它们不是巡视对象，不产生乡镇或村停留时间。

示例：

```json
{
  "depot": "O",
  "required_visit_order": ["A", "3"],
  "expanded_node_path": ["O", "U01", "A", "U01", "3", "O"]
}
```

上例表示实际通行路径为 `O -> U01 -> A -> U01 -> 3 -> O`，但真正的必访停留顺序只有 `A -> 3`。

## 2. RoutePlan

`RoutePlan` 表示一整套巡视方案。

必备字段：

| 字段 | 类型 | 含义 |
|---|---|---|
| `schema_version` | string | 契约版本，初始为 `route-plan-v1` |
| `plan_id` | string | 方案编号 |
| `source` | string | 方案来源，例如 `manual_fixture`、`nearest_neighbor`、`local_search` |
| `parameters` | object | 生成方案所用参数 |
| `routes` | list[Route] | 路线列表 |
| `metrics` | PlanMetrics or null | 全方案指标，可由 B 线复算 |

约束：

- `routes` 中的每条路线必须从 `O` 出发并回到 `O`。
- 乡镇与村节点必须在全方案中被覆盖一次。
- 辅助道路节点不得出现在 `required_visit_order` 中。
- 标为 nullable 的字段必须保留字段名，暂未计算时写为 `null`，不得省略字段。

## 3. Route

`Route` 表示一组巡视人员的单条闭合路线。

必备字段：

| 字段 | 类型 | 含义 |
|---|---|---|
| `route_id` | string | 路线编号 |
| `depot` | string | 出发和返回节点，固定为 `O` |
| `required_visit_order` | list[string] | 必访节点顺序，只包含乡镇和村 |
| `expanded_node_path` | list[string] or null | 原始路网上的实际通行节点序列，可以包含辅助道路节点 |
| `distance_km` | number or null | 路线行驶距离，可由 B 线复算 |
| `metrics` | RouteMetrics or null | 单路线指标，可由 B 线复算 |

约束：

- `expanded_node_path` 若存在，首尾必须都是 `O`。
- `required_visit_order` 不写首尾 `O`，也不得在中间写入 `O`；若出现 `O`，应视为契约错误。
- `required_visit_order` 只能包含乡镇节点和村节点；若出现 `U01`–`U05` 等辅助道路节点，应视为契约错误。
- 若 `expanded_node_path` 暂缺，B 线可以基于 `required_visit_order` 和最短路闭包复算展开路径。
- `expanded_node_path`、`distance_km`、`metrics` 等 nullable 字段暂缺值时写为 `null`，但字段本身不得省略。

## 4. RouteMetrics

`RouteMetrics` 表示单条路线的评价指标。

字段：

| 字段 | 类型 | 单位 | 含义 |
|---|---|---|---|
| `distance_km` | number | km | 行驶距离 |
| `travel_time_hour` | number | hour | 行驶时间 |
| `town_stop_time_hour` | number | hour | 乡镇停留时间 |
| `village_stop_time_hour` | number | hour | 村停留时间 |
| `total_stop_time_hour` | number | hour | 总停留时间 |
| `total_time_hour` | number | hour | 单路线总耗时 |

计算口径：

- `travel_time_hour = distance_km / speed_km_per_hour`
- `town_stop_time_hour = town_count * T`
- `village_stop_time_hour = village_count * t`
- `total_time_hour = travel_time_hour + total_stop_time_hour`

## 5. PlanMetrics

`PlanMetrics` 表示全方案指标。

字段：

| 字段 | 类型 | 单位 | 含义 |
|---|---|---|---|
| `group_count` | integer | none | 路线组数 |
| `total_distance_km` | number | km | 全部路线总路程 |
| `max_route_distance_km` | number | km | 最长单路线距离 |
| `min_route_distance_km` | number | km | 最短单路线距离 |
| `distance_range_km` | number | km | 路线距离极差 |
| `completion_time_hour` | number | hour | 完成时间，即最长单路线耗时 |
| `max_route_time_hour` | number | hour | 最长单路线耗时 |
| `time_range_hour` | number | hour | 单路线耗时极差 |
| `is_within_time_limit` | boolean | none | 是否满足给定时间上限 |

第 (1) 问默认用距离指标评价均衡性；第 (2)–(4) 问默认用耗时指标评价可行性和瓶颈。

## 6. AuditResult

`AuditResult` 表示 B 线对方案的审计结果。

字段：

| 字段 | 类型 | 含义 |
|---|---|---|
| `plan_id` | string | 被审计方案编号 |
| `schema_valid` | boolean | 字段和契约版本是否合法 |
| `coverage_valid` | boolean | 必访节点覆盖是否合法 |
| `route_valid` | boolean | 路线首尾、展开路径和节点语义是否合法 |
| `metric_valid` | boolean | 指标是否可复算且一致 |
| `errors` | list[string] | 必须修复的问题 |
| `warnings` | list[string] | 不阻断但需要关注的问题 |
| `recomputed_metrics` | PlanMetrics | B 线复算后的全方案指标 |

审计器必须给出具体错误原因，例如“村节点 `12` 未覆盖”“辅助节点 `U03` 出现在必访顺序中”“路线 `R2` 未返回 `O`”。

## 7. 最小样例

```json
{
  "schema_version": "route-plan-v1",
  "plan_id": "manual-smoke-001",
  "source": "manual_fixture",
  "parameters": {
    "T_hour": 2.0,
    "t_hour": 1.0,
    "speed_km_per_hour": 35.0,
    "time_limit_hour": 24.0
  },
  "routes": [
    {
      "route_id": "R1",
      "depot": "O",
      "required_visit_order": ["C", "A", "33"],
      "expanded_node_path": null,
      "distance_km": null,
      "metrics": null
    }
  ],
  "metrics": null
}
```

该样例不是最终路线，只用于验证 A/B 两线都能读写同一种结构。它属于 schema smoke 样例，不要求覆盖全部必访节点；完整覆盖样例应另行维护。

## 8. 实现落地方案

正式编码时按以下顺序落地：

1. 建立契约数据类或结构体，对应 `RoutePlan`、`Route`、`RouteMetrics`、`PlanMetrics`、`AuditResult`。
2. 建立 JSON/TSV 或对象序列化测试，确保字段名、单位和默认值稳定。
3. 编写最小样例方案测试，让 B 线审计器能读取 `manual-smoke-001`。
4. A 线的第一个路线构造器必须输出同样格式。
5. B 线对 A 线输出执行覆盖、路径、指标三类审计。
6. 后续任何算法只能扩展 `parameters` 或新增明确版本，不能破坏既有字段。
