# 应用层

本目录用于放置 GUI 或展示型入口。根据项目协议，GUI 只负责交互和展示；数学状态、参数校验、方法执行、IO 与计时归后端负责。

当前 B8 提供两个 GUI/展示入口：

- `apps/gui/route_animation_player.py`：无 GUI 重依赖的路线动画导出入口。它只加载已有 `RoutePlan`，调用 `mm_final.visualization` 后端导出 README、表格、帧、GIF 或无声 MP4，不运行或修改 A 线算法。
- `apps/gui/route_animation_gui.py`：B8c PySide6/Qt GUI 全栈问题解决器。它按第 (1)-(4) 问分 Tab，支持 `T/t/v/k` 参数设置、算法选择、后台求解、候选方案池、B3 final 诊断、B7 参数敏感性分析、路线播放、路线显隐、GIF/MP4 导出和 README/表格导出。
