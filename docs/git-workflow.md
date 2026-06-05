# Git 协作规范

本文档记录 A/B 双线并行开发时的 Git 分支与合并规则。

---

## 1. 基本原则

- `main` 是稳定主干，只合并已经通过测试、不会破坏对接契约的内容。
- A/B 工程师不在 `main` 上直接开发。
- A/B 工程师各自使用短生命周期功能分支，避免长期分叉。
- 共享契约和公共数据结构必须优先单独合并，不能夹带在 A 线或 B 线的功能分支中。

## 2. 分支命名

推荐分支前缀：

- `a/...`：A 线路线构造与空间优化任务，例如 `a/graph-model`、`a/single-route-builder`。
- `b/...`：B 线耗时审计、下界证明与参数分析任务，例如 `b/time-metrics`、`b/route-audit`。
- `shared/...`：共享契约、公共数据结构、公共测试夹具任务，例如 `shared/route-plan-model`、`shared/contract-tests`。

## 3. 共享契约优先规则

本项目最容易产生合并风险的文件包括：

- `docs/contracts/route-plan-contract.md`
- 未来的 `RoutePlan`、`Route`、`RouteMetrics`、`PlanMetrics`、`AuditResult` 数据类或结构体
- A/B 两线共同使用的测试夹具、样例方案和节点语义规则

规则：

1. 任何契约字段、单位、节点语义、审计口径变化，都先开 `shared/...` 分支。
2. `shared/...` 分支只做共享契约或公共结构改动，不混入 A/B 具体算法。
3. `shared/...` 经双方确认并合并进 `main` 后，A/B 两线再从最新 `main` 继续开发。
4. A/B 功能分支不得绕过已合并的共享契约，也不得私自维护另一套方案格式。

## 4. 合并流程

每个功能分支合并前建议执行：

1. 从 `main` 拉取最新内容。
2. 将最新 `main` 合入当前功能分支，提前解决冲突。
3. 运行当前阶段已有测试。
4. 确认不破坏 `docs/contracts/route-plan-contract.md` 定义的格式。
5. 合并回 `main`。

示例流程：

```powershell
git switch main
git pull
git switch a/single-route-builder
git merge main
# 解决冲突并运行测试
git switch main
git merge a/single-route-builder
git push
```

## 5. 冲突处理

若 A/B 两线发生冲突，按以下优先级处理：

1. 契约文档与公共数据结构优先保持一致。
2. 测试夹具和审计口径优先保持可复现。
3. A/B 各自算法实现可以调整以服从共享契约。

冲突解决后，应补充或更新测试，避免同类冲突在下一次合并时再次出现。

