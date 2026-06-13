# 应用层

本目录用于放置 GUI 或展示型入口。根据项目协议，GUI 只负责交互和展示；数学状态、参数校验、方法执行、IO 与计时归后端负责。

当前 B8 第一版提供 `apps/gui/route_animation_player.py` 作为无 GUI 重依赖的路线动画导出入口。它只加载已有 `RoutePlan`，调用 `mm_final.visualization` 后端导出 README、表格、帧、GIF 或无声 MP4，不运行或修改 A 线算法。
