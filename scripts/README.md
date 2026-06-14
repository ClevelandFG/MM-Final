# 脚本目录

本目录用于放置工程辅助脚本，例如数据校验、结果导出、批量实验执行等。核心算法应保留在 `src/`，脚本只负责调度。

## 第 (4) 问参数网格批量重优化

`run_parameter_batch.py` 用于独立于 GUI 在命令行中运行第 (4) 问批量实验。默认固定巡视组数 `k=3`，对

- `T = 1.0, 1.5, 2.0, 2.5, 3.0`
- `t = 0.5, 1.0, 1.5`
- `v = 25, 30, 35, 40, 45`

共 `5 x 3 x 5 = 75` 组参数逐点重新优化，目标是在固定组数下最小化最大单路线完成时间。

默认运行：

```powershell
uv run python scripts\run_parameter_batch.py
```

脚本会显示进度，例如 `已计算：34/75`。默认输出目录为 `outputs/parameter_batch/`，其中：

- `batch_results.csv`：用于后续绘制热力图的主表。
- `batch_results.json`：完整批量结果。
- `summary.md`：简短文字摘要。
- `plans/`：每个参数点对应的 `RoutePlan` JSON。

常用参数示例：

```powershell
uv run python scripts\run_parameter_batch.py --time-limit-seconds 120 --iterations 80
uv run python scripts\run_parameter_batch.py --T-values 1.5,2,2.5 --t-values 0.5,1,1.5 --v-values 25,35,45
uv run python scripts\run_parameter_batch.py --dry-run
```

结果属于启发式重优化结果；若报告中需要写成强最优结论，还需要额外证明或更强求解器支持。
