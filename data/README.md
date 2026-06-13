# 数据目录

- `raw/`：原始题目数据，原则上不在实现过程中修改。
- `processed/`：由程序生成或清洗后的中间数据。

## 已纳入数据

- `raw/road_network.tsv`：题面道路网络的结构化边表，是算法、审计和测试的权威路网输入。
- `processed/road_network_layout/straight-line-layout-source.png`：由题面原图手动转化得到的直线拓扑图，仅作为 B8 可视化布局复原和人工复核底图，不参与距离或路径计算。
- `processed/road_network_layout/original-map-layout.json`：由直线拓扑图半手工标注得到的归一化节点坐标，供 B8 路线图、动画和 GUI 优先使用；该布局不是地理坐标，边几何由 `road_network.tsv` 决定。
