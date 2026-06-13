# MM-Final

本项目用于完成县域乡镇村道路巡检路线优化建模任务。核心资料见 `docs/task.md` 与 `docs/theories.md`。

当前仓库已完成工程初始化、路网公共底基、路线方案契约、A/B 线核心求解与 B8b 路线动画 GUI 的阶段性实现；后续重点转向 GUI 问题解决器、结果打磨、报告资产和展示支撑。

## GUI 当前入口

B8b 当前提供的是 PySide6/Qt 路线动画播放器：用于加载已有 `RoutePlan` JSON，播放路线巡视过程，并导出 GIF 或无声 MP4。它是可视化入口，不是完整问题解决器；B8c 将升级为覆盖题目选择、参数调整、算法选择、求解触发、审计诊断、图表展示和结果导出的全栈 GUI。

首次使用先同步可视化和 GUI 依赖：

```powershell
uv sync --extra viz --extra gui
```

启动空白播放器：

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m apps.gui.route_animation_gui
```

也可以启动时直接加载一个路线方案：

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m apps.gui.route_animation_gui tests\fixtures\route_plans\full-coverage-smoke-001.json
```

基本操作：

- 点击“加载”选择 `RoutePlan` JSON；未通过 B3 final 审计的方案会显示 `CONTRACT MISMATCH`，不能进入正式播放。
- 使用“播放 / 暂停”“重置”和进度条查看任意模型时刻；默认播放比例为真实 1 秒代表模型 1 小时，可用倍速控件调整。
- 右侧“路线显隐”可单独开关各巡视队伍；当前帧、GIF 和 MP4 导出都会沿用该显隐设置。
- “导出 GIF”“导出 MP4”用于动画文件；“导出 README/表格”用于生成可复核的导出包。
