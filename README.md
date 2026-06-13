# MM-Final

本项目用于完成县域乡镇村道路巡检路线优化建模任务。核心资料见 `docs/task.md` 与 `docs/theories.md`。

当前仓库已完成工程初始化、路网公共底基、路线方案契约、A/B 线核心求解与 B8b 路线动画 GUI 的阶段性实现；后续重点转向 GUI 问题解决器、结果打磨、报告资产和展示支撑。

## GUI 全栈问题解决器

B8c 当前提供 PySide6/Qt GUI 全栈问题解决器：覆盖第 (1)-(4) 问 Tab、`T/t/v/k` 参数设置、算法选择、后台求解、候选方案池、审计诊断、路线动画播放和结果导出。它通过共享 `AlgorithmRunner` / `SolveJob` 契约调用后端，不在 GUI 内编写核心数学逻辑。

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

- 在第 (1)-(3) 问 Tab 设置参数并点击“运行”，GUI 会在后台调用后端 solver 并把结果加入候选方案池。
- 第 (4) 问可对候选方案池运行参数敏感性分析，结果显示在运行日志区。
- 点击“加载”选择 `RoutePlan` JSON；未通过 B3 final 审计的方案会显示 `CONTRACT MISMATCH`，不能进入正式播放。
- 使用“播放 / 暂停”“重置”和进度条查看任意模型时刻；默认播放比例为真实 1 秒代表模型 1 小时，可用倍速控件调整。
- 右侧“路线显隐”可单独开关各巡视队伍；当前帧、GIF 和 MP4 导出都会沿用该显隐设置。
- “导出 GIF”“导出 MP4”用于动画文件；“导出 README/表格”用于生成可复核的导出包。
