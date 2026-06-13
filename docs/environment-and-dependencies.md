# Python 环境与依赖策略

本文档记录 Python 虚拟环境、依赖管理、GUI 与可视化相关决策。尚未拍板的内容保留为待确认，不作为实施规则。

---

## 1. 已确认决策

### 1.1 依赖配置方式

采用 `pyproject.toml` 作为项目元数据、依赖声明和工具配置入口。

执行含义：

- 已建立 `pyproject.toml`，依赖声明只以 `pyproject.toml` 为主入口。
- 运行依赖写入 `[project].dependencies`。
- 可选功能依赖写入 `[project.optional-dependencies]`，例如 `gui`、`viz`、`dev`。
- 暂不新增 `requirements.txt` 作为主依赖清单。

### 1.2 环境复现方式

采用 uv 管理虚拟环境同步和锁文件。

执行含义：

- `pyproject.toml` 记录项目元数据、依赖声明和工具配置。
- `uv.lock` 记录解析后的依赖版本，应纳入 Git。
- `.venv` 是本机虚拟环境目录，不纳入 Git。
- 其他开发者拉取仓库后，通过 uv 根据 `pyproject.toml` 和 `uv.lock` 重建本机环境。
- 这种方式保证依赖版本和功能环境一致，但不追求复制完全相同的 `.venv` 目录字节内容。
- 环境创建命令和注意事项见 `docs/setup-python-env.md`。

### 1.3 GUI 策略

核心算法阶段不以 GUI 为第一目标。先完成命令行、数据输出、审计报告和可复用可视化后端；B8 阶段再在该后端之上实现轻量 GUI 播放器。

执行含义：

- 后端继续负责数学状态、参数校验、方法执行、IO 和计时。
- GUI 只负责文件加载、参数输入、求解触发、路线播放、图表展示和结果导出。
- B8b 第一版 GUI 需要支持可拖动进度条和逐帧动画播放，优先评估 PySide6/Qt 一类桌面播放器；Streamlit 保留给后续报告查看器或轻量仪表盘，不作为第一版路线动画播放器首选。

### 1.4 核心算法依赖

核心图算法和数值计算依赖如下：

- `networkx`：已作为主依赖加入。
- `numpy`
- `scipy`

执行含义：

- NetworkX 用于路网建模、连通性校验、后续最短路和基础图算法。
- NumPy/SciPy 用于数值计算、矩阵/数组处理和后续可能的优化支持。
- OR-Tools 等专业优化库暂不作为初始依赖，只有当启发式和基础优化不足时再评估。

### 1.5 Git 分支

环境和依赖配置属于 A/B 共享基础，走 `shared/...` 分支。

执行含义：

- 初始化 `pyproject.toml`、调整依赖、改变虚拟环境说明时，使用类似 `shared/python-env-setup` 的分支。
- 依赖变更不得夹带在 A 线或 B 线功能分支中。

### 1.6 GUI、报告与展示分工

除 A/B 主线外，后续还有三项交付任务：

- GUI 与可视化：B 线工程师负责。
- 上台展示：A 线工程师负责。
- 书面报告：两人共同完成，各自负责自己工作内容对应的报告部分。

### 1.7 可视化依赖栈

采用 Matplotlib + NetworkX + Pillow/ImageIO + Plotly 的组合；MP4 导出采用 ImageIO 的 `imageio[ffmpeg]` / `imageio-ffmpeg` 路线，GUI 框架依赖暂不锁死。

执行含义：

- Matplotlib + NetworkX 用于报告级静态路网图、路线组高亮图和基础动画。
- Pillow/ImageIO 用于优先支持 GIF、逐帧图像导出和视频帧写入。
- Plotly 用于后续交互式图表和网络图展示，例如路线组开关、悬停查看节点信息、瓶颈路线高亮。
- Streamlit 暂不作为初始依赖；如后续需要轻量 Web 报告查看器，再放入 `gui` 可选依赖组。
- PySide6/Qt 暂不作为初始依赖；若 B8b 最终确认采用桌面播放器，再放入 `gui` 可选依赖组。
- 无声 MP4 已确认为需求，采用 `imageio[ffmpeg]` / `imageio-ffmpeg`，避免第一版直接依赖系统级 FFmpeg 或 PyAV。

### 1.8 可选依赖分组

后续 `pyproject.toml` 中依赖分组建议如下：

- 主依赖：核心建模、算法和审计所需依赖，例如 `networkx`、`numpy`、`scipy`。
- `viz`：报告图、基础动画、GIF 和无声 MP4 导出相关依赖，例如 `matplotlib`、`pillow`、`imageio`、`imageio[ffmpeg]` 或 `imageio-ffmpeg`，Plotly 可在交互图阶段加入。
- `gui`：轻量 GUI 相关依赖，例如后续可能加入的 `PySide6` 或 `streamlit`。
- `video` 扩展项可后置；第一版若不单列 `video`，则把 `imageio[ffmpeg]` / `imageio-ffmpeg` 放入 `viz` optional extra。
- `dev`：测试、格式化、类型检查等开发依赖。

### 1.9 动态展示目标

第一阶段动态展示目标为路线动画时间轴 + 静态图 + GIF：

- 静态图用于书面报告和阶段性检查。
- 路线动画时间轴用于支撑 GUI 播放器、拖动进度条、任意时刻截图和导出动画。
- GIF 用于直观看到路网巡视过程，优先服务上台展示和讨论。
- 无声 MP4 用于 LaTeX 报告嵌入，依赖方案为 `imageio[ffmpeg]` / `imageio-ffmpeg`。

## 2. 待确认决策

### 2.1 Python 版本

等待 A 线工程师确认。当前 `pyproject.toml` 暂以 `requires-python >=3.9` 保持兼容，便于 A 线工程师在升级前也能运行基础契约测试。

建议后续统一到 Python 3.12.x；统一后再将 `requires-python` 收紧为 3.12 相关下界，并重新生成 `uv.lock`。

## 3. 可视化初步调研结论

### 3.1 Matplotlib

定位：

- 适合生成报告图。
- 支持静态、动画和交互式可视化。
- 可通过动画接口导出 GIF 或 MP4。

项目适配：

- 适合作为第一阶段报告图和路线过程动画的基础工具。
- 对本项目规模足够。
- 需要导出 MP4 时通常依赖 FFmpeg 可执行程序；导出 GIF 可优先考虑 Pillow writer。

### 3.2 NetworkX

定位：

- 适合图建模、图算法和基础图绘制。
- 官方定位更偏图分析，不是专业图可视化工具。

项目适配：

- 对本项目是刚需级依赖，因为路网本身就是无向加权图。
- 绘图可用于初版路网图、路线高亮图和调试图。
- 若最终展示要求更精美，需要配合 Matplotlib 或 Plotly 做样式加工。

### 3.3 Plotly

定位：

- 适合交互式图表。
- 支持网络图和动画，但更偏浏览器内交互展示。

项目适配：

- 已确认纳入可视化依赖栈，但建议作为 `viz` 可选依赖，不作为核心算法依赖。
- 适合后续交互需求：悬停查看节点信息、路线组开关、参数变化对比、瓶颈路线高亮。
- 若只需要报告静态图和 GIF，Matplotlib 仍是首选输出工具；Plotly 主要服务交互查看。

### 3.4 Streamlit

定位：

- 适合快速搭建轻量 Web GUI。
- 可承载 Matplotlib、Plotly、表格和参数控件。

项目适配：

- 适合作为后续报告查看器或轻量仪表盘方案。
- 对“进度条拖动 + 帧级动画播放器 + 本地导出”的第一版 B8b 需求不是首选。
- 不适合作为算法核心依赖。
- 依赖链比 Matplotlib/NetworkX 更重，建议放入可选依赖组。

### 3.5 ImageIO / Pillow / FFmpeg

定位：

- Pillow/ImageIO 适合图片和 GIF 导出。
- FFmpeg 适合 MP4 或更稳定的视频导出，但可能涉及系统级可执行文件或 Python 包内置二进制。

项目适配：

- GIF 导出建议优先使用 Pillow 或 ImageIO。
- MP4 导出选择 ImageIO `imageio[ffmpeg]` / `imageio-ffmpeg` 路线；Matplotlib `FFMpegWriter` + 系统 FFmpeg 和 PyAV 不作为第一版首选。
- `imageio-ffmpeg` 依赖更接近 Python 环境内部管理，但仍应把视频导出测试设计成可跳过或最小 smoke，避免个别平台编码器不可用时阻塞核心测试。
- MP4 默认应导出无声视频；只有调用方显式提供音频路径时才考虑音轨。

### 3.6 PySide6 / Qt

定位：

- 适合实现桌面 GUI、播放控制、可拖动进度条和本地图像刷新。

项目适配：

- 更贴近 B8b 的路线动画播放器需求。
- 依赖体积比纯可视化库更重，只能作为 `gui` 可选依赖，不能进入核心算法依赖。
- 第一版若采用 PySide6，应保持 GUI 只消费 `mm_final.visualization` 的 timeline 和 frame renderer，不在 GUI 内写数学逻辑。
