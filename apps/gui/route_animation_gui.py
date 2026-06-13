"""B8c PySide6/Qt GUI 全栈问题解决器。"""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile
import time
from typing import Any, Optional

from mm_final.evaluation.parameter_sensitivity import (
    analyze_parameter_sensitivity,
    sensitivity_report_to_markdown,
)
from mm_final.solving import CancelToken, DefaultAlgorithmRunner, ProblemKind, SolveJob, SolveParameters, SolveResult
from mm_final.visualization import (
    RenderOptions,
    export_animation_gif,
    export_animation_mp4,
    render_snapshot_png,
)
from mm_final.visualization.exports import RouteAnimationBundle, VisualizationInputError, export_route_animation_package


def _import_qt():
    try:
        from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
        from PySide6.QtGui import QPixmap
        from PySide6.QtWidgets import (
            QApplication,
            QCheckBox,
            QComboBox,
            QDoubleSpinBox,
            QFileDialog,
            QFormLayout,
            QFrame,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QListWidget,
            QListWidgetItem,
            QMainWindow,
            QMessageBox,
            QProgressBar,
            QPushButton,
            QScrollArea,
            QSlider,
            QSpinBox,
            QTabWidget,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )
    except ImportError as exc:  # pragma: no cover - 由 gui extra 提供
        raise ImportError("PySide6 is required for the B8 GUI. Install the 'gui' extra.") from exc
    return {
        "QObject": QObject,
        "Qt": Qt,
        "QThread": QThread,
        "QTimer": QTimer,
        "Signal": Signal,
        "QPixmap": QPixmap,
        "QApplication": QApplication,
        "QCheckBox": QCheckBox,
        "QComboBox": QComboBox,
        "QDoubleSpinBox": QDoubleSpinBox,
        "QFileDialog": QFileDialog,
        "QFormLayout": QFormLayout,
        "QFrame": QFrame,
        "QHBoxLayout": QHBoxLayout,
        "QLabel": QLabel,
        "QLineEdit": QLineEdit,
        "QListWidget": QListWidget,
        "QListWidgetItem": QListWidgetItem,
        "QMainWindow": QMainWindow,
        "QMessageBox": QMessageBox,
        "QProgressBar": QProgressBar,
        "QPushButton": QPushButton,
        "QScrollArea": QScrollArea,
        "QSlider": QSlider,
        "QSpinBox": QSpinBox,
        "QTabWidget": QTabWidget,
        "QTextEdit": QTextEdit,
        "QVBoxLayout": QVBoxLayout,
        "QWidget": QWidget,
    }


qt = _import_qt()
QObject = qt["QObject"]
Qt = qt["Qt"]
QThread = qt["QThread"]
QTimer = qt["QTimer"]
Signal = qt["Signal"]
QPixmap = qt["QPixmap"]
QApplication = qt["QApplication"]
QCheckBox = qt["QCheckBox"]
QComboBox = qt["QComboBox"]
QDoubleSpinBox = qt["QDoubleSpinBox"]
QFileDialog = qt["QFileDialog"]
QFormLayout = qt["QFormLayout"]
QFrame = qt["QFrame"]
QHBoxLayout = qt["QHBoxLayout"]
QLabel = qt["QLabel"]
QLineEdit = qt["QLineEdit"]
QListWidget = qt["QListWidget"]
QListWidgetItem = qt["QListWidgetItem"]
QMainWindow = qt["QMainWindow"]
QMessageBox = qt["QMessageBox"]
QProgressBar = qt["QProgressBar"]
QPushButton = qt["QPushButton"]
QScrollArea = qt["QScrollArea"]
QSlider = qt["QSlider"]
QSpinBox = qt["QSpinBox"]
QTabWidget = qt["QTabWidget"]
QTextEdit = qt["QTextEdit"]
QVBoxLayout = qt["QVBoxLayout"]
QWidget = qt["QWidget"]


class _SolveWorker(QObject):
    event = Signal(object)
    finished = Signal(object)

    def __init__(self, job: SolveJob, cancel_token: CancelToken):
        super().__init__()
        self.job = job
        self.cancel_token = cancel_token
        self.runner = DefaultAlgorithmRunner()

    def run(self) -> None:
        result = self.runner.run(self.job, event_sink=self.event.emit, cancel_token=self.cancel_token)
        self.finished.emit(result)


class RouteAnimationWindow(QMainWindow):
    """B8c 问题解决器窗口，复用 B8b 动画播放器能力。"""

    slider_scale = 1000

    def __init__(self, route_plan_path: Optional[Path] = None):
        super().__init__()
        self.setWindowTitle("Road Problem Solver")
        self.resize(1380, 900)

        self.bundle: Optional[RouteAnimationBundle] = None
        self.road_network = None
        self.route_plan_path: Optional[Path] = None
        self.temp_dir = tempfile.TemporaryDirectory(prefix="mm-final-b8c-gui-")
        self.current_time_hour = 0.0
        self.playback_model_hours_per_second = 1.0
        self._last_tick = time.monotonic()
        self._syncing_slider = False
        self.route_checkboxes: dict[str, QCheckBox] = {}
        self.current_frame_pixmap: Optional[QPixmap] = None
        self.problem_controls: dict[str, dict[str, Any]] = {}
        self.solve_results: list[SolveResult] = []
        self.candidate_plan_paths: dict[str, Path] = {}
        self.solve_thread: Optional[QThread] = None
        self.solve_worker: Optional[_SolveWorker] = None
        self.cancel_token: Optional[CancelToken] = None

        self._build_ui()
        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self._advance_playback)

        if route_plan_path is not None:
            self.load_route_plan(route_plan_path)

    def closeEvent(self, event):  # noqa: N802 - Qt 命名约定
        if self.cancel_token is not None:
            self.cancel_token.request_cancel()
        self.temp_dir.cleanup()
        super().closeEvent(event)

    def resizeEvent(self, event):  # noqa: N802 - Qt 命名约定
        super().resizeEvent(event)
        self._rescale_current_frame()

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)

        self.warning_label = QLabel("未加载路线方案")
        self.warning_label.setFrameShape(QFrame.Shape.Panel)
        self.warning_label.setStyleSheet("padding: 8px; background: #fff4ce; color: #4f3b00;")
        root.addWidget(self.warning_label)

        self.problem_tabs = QTabWidget()
        self.problem_tabs.addTab(self._make_problem_tab("fixed_groups", "mtsp_local_search", 3), "第(1)问 固定组")
        self.problem_tabs.addTab(self._make_problem_tab("minimum_groups", "min_groups_search", 8), "第(2)问 最少组")
        self.problem_tabs.addTab(self._make_problem_tab("unlimited_personnel", "minmax_vrp_search", 8), "第(3)问 最短时间")
        self.problem_tabs.addTab(self._make_sensitivity_tab(), "第(4)问 参数敏感性")
        root.addWidget(self.problem_tabs)

        file_row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("选择 RoutePlan JSON")
        browse_button = QPushButton("加载")
        browse_button.clicked.connect(self._browse_route_plan)
        self.cancel_button = QPushButton("取消求解")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel_solve)
        self.solve_progress = QProgressBar()
        self.solve_progress.setRange(0, 100)
        self.solve_progress.setValue(0)
        file_row.addWidget(self.path_edit, 1)
        file_row.addWidget(browse_button)
        file_row.addWidget(self.cancel_button)
        file_row.addWidget(self.solve_progress)
        root.addLayout(file_row)

        body = QHBoxLayout()
        image_panel = QVBoxLayout()
        self.image_label = QLabel("加载合法 RoutePlan 后显示动画帧")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(760, 500)
        self.image_scroll = QScrollArea()
        self.image_scroll.setWidgetResizable(True)
        self.image_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_scroll.setWidget(self.image_label)
        image_panel.addWidget(self.image_scroll, 1)

        control_row = QHBoxLayout()
        self.play_button = QPushButton("播放")
        self.play_button.clicked.connect(self.toggle_playback)
        reset_button = QPushButton("重置")
        reset_button.clicked.connect(lambda: self.set_time_hour(0.0))
        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.setRange(0, self.slider_scale)
        self.time_slider.valueChanged.connect(self._slider_changed)
        self.time_label = QLabel("0.00 h / 0.00 h")
        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0.1, 20.0)
        self.speed_spin.setSingleStep(0.5)
        self.speed_spin.setValue(1.0)
        self.speed_spin.setSuffix("x")
        control_row.addWidget(self.play_button)
        control_row.addWidget(reset_button)
        control_row.addWidget(self.time_slider, 1)
        control_row.addWidget(self.time_label)
        control_row.addWidget(QLabel("倍速"))
        control_row.addWidget(self.speed_spin)
        image_panel.addLayout(control_row)

        export_row = QHBoxLayout()
        gif_button = QPushButton("导出 GIF")
        gif_button.clicked.connect(lambda: self._export_animation("gif"))
        mp4_button = QPushButton("导出 MP4")
        mp4_button.clicked.connect(lambda: self._export_animation("mp4"))
        package_button = QPushButton("导出 README/表格")
        package_button.clicked.connect(self._export_package)
        export_row.addWidget(gif_button)
        export_row.addWidget(mp4_button)
        export_row.addWidget(package_button)
        export_row.addStretch(1)
        image_panel.addLayout(export_row)

        side_panel = QVBoxLayout()
        side_panel.addWidget(QLabel("候选方案池"))
        self.candidate_list = QListWidget()
        self.candidate_list.currentItemChanged.connect(lambda current, _previous: self._load_candidate_item(current))
        side_panel.addWidget(self.candidate_list, 1)
        side_panel.addWidget(QLabel("路线显隐"))
        self.route_list_widget = QWidget()
        self.route_list_layout = QVBoxLayout(self.route_list_widget)
        self.route_list_layout.addStretch(1)
        side_panel.addWidget(self.route_list_widget)
        side_panel.addWidget(QLabel("审计诊断"))
        self.diagnostic_list = QListWidget()
        side_panel.addWidget(self.diagnostic_list, 1)
        side_panel.addWidget(QLabel("运行日志"))
        self.solve_log = QTextEdit()
        self.solve_log.setReadOnly(True)
        side_panel.addWidget(self.solve_log, 1)

        body.addLayout(image_panel, 4)
        body.addLayout(side_panel, 2)
        root.addLayout(body, 1)
        self.setCentralWidget(central)

    def _make_problem_tab(self, problem_kind: ProblemKind, algorithm_id: str, default_k: int) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()
        controls: dict[str, Any] = {}
        controls["T_hour"] = _double_spin(0.0, 12.0, 2.0, " h")
        controls["t_hour"] = _double_spin(0.0, 12.0, 1.0, " h")
        controls["speed_km_per_hour"] = _double_spin(1.0, 120.0, 35.0, " km/h")
        controls["group_count"] = QSpinBox()
        controls["group_count"].setRange(1, 60)
        controls["group_count"].setValue(default_k)
        controls["algorithm"] = QComboBox()
        controls["algorithm"].addItem("默认后端算法", "default")
        controls["algorithm"].addItem(algorithm_id, algorithm_id)
        form.addRow("乡镇停留 T", controls["T_hour"])
        form.addRow("村停留 t", controls["t_hour"])
        form.addRow("车速 v", controls["speed_km_per_hour"])
        form.addRow("组数 k / 上限", controls["group_count"])
        form.addRow("算法", controls["algorithm"])
        layout.addLayout(form)
        run_button = QPushButton("运行")
        run_button.clicked.connect(lambda _checked=False, kind=problem_kind: self._start_solve(kind))
        controls["run_button"] = run_button
        layout.addWidget(run_button)
        layout.addStretch(1)
        self.problem_controls[problem_kind] = controls
        return tab

    def _make_sensitivity_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        run_button = QPushButton("分析候选池")
        run_button.clicked.connect(self._run_sensitivity_analysis)
        layout.addWidget(run_button)
        layout.addStretch(1)
        return tab

    def _browse_route_plan(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择 RoutePlan JSON", "", "JSON (*.json)")
        if path:
            self.load_route_plan(Path(path))

    def load_route_plan(self, path: Path) -> bool:
        """加载 RoutePlan 并进入播放状态。"""

        self.timer.stop()
        self.play_button.setText("播放")
        self.path_edit.setText(str(path))
        self.route_plan_path = path
        try:
            load_output_dir = Path(self.temp_dir.name) / f"load-{int(time.time() * 1000)}"
            result = export_route_animation_package(path, load_output_dir, strict_final=True)
        except VisualizationInputError as exc:
            self.bundle = None
            self.road_network = None
            self._show_rejection(exc)
            return False

        self.bundle = result.bundle
        self.road_network = self._load_default_road_network()
        self.current_time_hour = 0.0
        self._populate_routes()
        self._populate_diagnostics()
        self._set_warning_status()
        self.set_time_hour(0.0)
        return True

    def toggle_playback(self) -> None:
        if self.bundle is None:
            return
        if self.timer.isActive():
            self.timer.stop()
            self.play_button.setText("播放")
        else:
            self._last_tick = time.monotonic()
            self.timer.start()
            self.play_button.setText("暂停")

    def set_time_hour(self, time_hour: float) -> None:
        if self.bundle is None:
            return
        completion = self.bundle.timeline.completion_time_hour
        self.current_time_hour = min(max(time_hour, 0.0), completion)
        self._sync_slider()
        self._render_current_frame()

    def visible_route_ids(self) -> frozenset[str]:
        return frozenset(route_id for route_id, checkbox in self.route_checkboxes.items() if checkbox.isChecked())

    def _slider_changed(self, value: int) -> None:
        if self._syncing_slider or self.bundle is None:
            return
        completion = self.bundle.timeline.completion_time_hour
        self.set_time_hour(completion * value / self.slider_scale)

    def _advance_playback(self) -> None:
        if self.bundle is None:
            return
        now = time.monotonic()
        elapsed_second = now - self._last_tick
        speed = float(self.speed_spin.value())
        self.set_time_hour(self.current_time_hour + elapsed_second * self.playback_model_hours_per_second * speed)
        self._last_tick = time.monotonic()
        if self.current_time_hour >= self.bundle.timeline.completion_time_hour:
            self.timer.stop()
            self.play_button.setText("播放")

    def _sync_slider(self) -> None:
        if self.bundle is None:
            return
        completion = self.bundle.timeline.completion_time_hour
        ratio = 0.0 if completion <= 0 else self.current_time_hour / completion
        self._syncing_slider = True
        self.time_slider.setValue(round(ratio * self.slider_scale))
        self._syncing_slider = False
        self.time_label.setText(f"{self.current_time_hour:.2f} h / {completion:.2f} h")

    def _render_current_frame(self) -> None:
        if self.bundle is None:
            return
        frame_path = Path(self.temp_dir.name) / "current-frame.png"
        render_snapshot_png(
            self.bundle.timeline,
            self._road_network(),
            self.bundle.layout,
            frame_path,
            time_hour=self.current_time_hour,
            options=RenderOptions(visible_route_ids=self.visible_route_ids()),
        )
        pixmap = QPixmap(str(frame_path))
        self._show_frame_pixmap(pixmap)

    def _show_frame_pixmap(self, pixmap: QPixmap) -> None:
        self.current_frame_pixmap = pixmap
        self._rescale_current_frame()

    def _rescale_current_frame(self) -> None:
        if not hasattr(self, "image_scroll"):
            return
        if self.current_frame_pixmap is None or self.current_frame_pixmap.isNull():
            return
        viewport_size = self.image_scroll.viewport().size()
        if viewport_size.width() <= 0 or viewport_size.height() <= 0:
            return
        scaled = self.current_frame_pixmap.scaled(
            viewport_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)

    def _road_network(self):
        if self.road_network is not None:
            return self.road_network
        self.road_network = self._load_default_road_network()
        return self.road_network

    def _load_default_road_network(self):
        from mm_final.network import load_road_network

        result = load_road_network()
        if result.network is None:
            raise RuntimeError("Default road network failed to load.")
        return result.network

    def _start_solve(self, problem_kind: ProblemKind) -> None:
        if self.solve_thread is not None:
            QMessageBox.warning(self, "求解中", "当前已有求解任务在运行。")
            return
        job = self._build_solve_job(problem_kind)
        self.cancel_token = CancelToken()
        self.solve_worker = _SolveWorker(job, self.cancel_token)
        self.solve_thread = QThread(self)
        self.solve_worker.moveToThread(self.solve_thread)
        self.solve_thread.started.connect(self.solve_worker.run)
        self.solve_worker.event.connect(self._handle_solve_event)
        self.solve_worker.finished.connect(self._handle_solve_finished)
        self.solve_worker.finished.connect(self.solve_thread.quit)
        self.solve_thread.finished.connect(self.solve_worker.deleteLater)
        self.solve_thread.finished.connect(self._clear_solve_thread)
        self.solve_progress.setValue(0)
        self._set_solving_enabled(False)
        self._append_log(f"提交任务 {job.job_id}")
        self.solve_thread.start()

    def _build_solve_job(self, problem_kind: ProblemKind) -> SolveJob:
        controls = self.problem_controls[problem_kind]
        group_value = int(controls["group_count"].value())
        parameters = SolveParameters(
            T_hour=float(controls["T_hour"].value()),
            t_hour=float(controls["t_hour"].value()),
            speed_km_per_hour=float(controls["speed_km_per_hour"].value()),
            group_count=group_value,
            max_group_upper=group_value,
        )
        algorithm_id = controls["algorithm"].currentData()
        return SolveJob(
            job_id=f"{problem_kind}-{int(time.time())}",
            problem_kind=problem_kind,
            algorithm_id="default" if algorithm_id is None else str(algorithm_id),
            parameters=parameters,
            plan_id=f"{problem_kind}-{int(time.time())}",
        )

    def _cancel_solve(self) -> None:
        if self.cancel_token is not None:
            self.cancel_token.request_cancel()
            self._append_log("已请求取消；当前算法会在阶段边界响应。")

    def _handle_solve_event(self, event) -> None:
        if event.progress is not None:
            self.solve_progress.setValue(round(float(event.progress) * 100))
        self._append_log(event.message)

    def _handle_solve_finished(self, result: SolveResult) -> None:
        self._set_solving_enabled(True)
        self.solve_progress.setValue(100 if result.status == "completed" else self.solve_progress.value())
        self._append_log(f"任务结束：{result.status}")
        if result.status == "completed":
            self.solve_results.append(result)
            self._add_solve_result(result)
        elif result.error:
            QMessageBox.warning(self, "求解失败", result.error)

    def _clear_solve_thread(self) -> None:
        if self.solve_thread is not None:
            self.solve_thread.deleteLater()
        self.solve_thread = None
        self.solve_worker = None
        self.cancel_token = None

    def _set_solving_enabled(self, enabled: bool) -> None:
        for controls in self.problem_controls.values():
            controls["run_button"].setEnabled(enabled)
        self.cancel_button.setEnabled(not enabled)

    def _add_solve_result(self, result: SolveResult) -> None:
        selected_item = None
        for candidate in result.candidates:
            path = self._write_candidate_plan(candidate.plan_id, candidate.plan)
            self.candidate_plan_paths[candidate.plan_id] = path
            metrics = candidate.audit_result.recomputed_metrics
            completion = "n/a" if metrics is None else f"{metrics.completion_time_hour:.2f}h"
            item = QListWidgetItem(f"{candidate.plan_id} | {completion} | final={candidate.is_final_valid}")
            item.setData(Qt.ItemDataRole.UserRole, candidate.plan_id)
            self.candidate_list.addItem(item)
            if candidate.plan_id == result.recommended_plan_id:
                selected_item = item
        if selected_item is not None:
            self.candidate_list.setCurrentItem(selected_item)

    def _load_candidate_item(self, item) -> None:
        if item is None:
            return
        plan_id = item.data(Qt.ItemDataRole.UserRole)
        path = self.candidate_plan_paths.get(str(plan_id))
        if path is not None:
            self.load_route_plan(path)

    def _write_candidate_plan(self, plan_id: str, plan) -> Path:
        path = Path(self.temp_dir.name) / f"{_safe_filename(plan_id)}.json"
        with path.open("w", encoding="utf-8") as handle:
            json.dump(_jsonable(asdict(plan)), handle, ensure_ascii=False, indent=2)
        return path

    def _run_sensitivity_analysis(self) -> None:
        plans = [candidate.plan for result in self.solve_results for candidate in result.candidates if candidate.is_final_valid]
        if self.bundle is not None and all(plan.plan_id != self.bundle.plan.plan_id for plan in plans):
            plans.append(self.bundle.plan)
        if not plans:
            QMessageBox.warning(self, "缺少候选方案", "请先运行求解或加载合法 RoutePlan。")
            return
        try:
            report = analyze_parameter_sensitivity(self._road_network(), candidate_plans=plans)
        except Exception as exc:
            QMessageBox.warning(self, "分析失败", str(exc))
            return
        self.solve_log.setPlainText(sensitivity_report_to_markdown(report))
        self._append_log(f"参数敏感性分析完成：{len(report.scenario_summaries)} 个情景")

    def _populate_routes(self) -> None:
        while self.route_list_layout.count() > 1:
            item = self.route_list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.route_checkboxes.clear()
        if self.bundle is None:
            return
        for route_id in self.bundle.timeline.segments_by_route_id.keys():
            checkbox = QCheckBox(route_id)
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(lambda _state: self._render_current_frame())
            self.route_checkboxes[route_id] = checkbox
            self.route_list_layout.insertWidget(self.route_list_layout.count() - 1, checkbox)

    def _populate_diagnostics(self) -> None:
        self.diagnostic_list.clear()
        if self.bundle is None:
            return
        audit = self.bundle.audit_result
        self.diagnostic_list.addItem(f"schema_valid: {audit.schema_valid}")
        self.diagnostic_list.addItem(f"coverage_valid: {audit.coverage_valid}")
        self.diagnostic_list.addItem(f"route_valid: {audit.route_valid}")
        self.diagnostic_list.addItem(f"metric_valid: {audit.metric_valid}")
        for warning in audit.warnings:
            self.diagnostic_list.addItem(f"WARNING: {warning}")
        for error in audit.errors:
            self.diagnostic_list.addItem(f"ERROR: {error}")

    def _show_rejection(self, exc: VisualizationInputError) -> None:
        self.warning_label.setText(f"CONTRACT MISMATCH: {exc}")
        self.warning_label.setStyleSheet("padding: 8px; background: #ffe1e1; color: #8a0000; font-weight: bold;")
        self.image_label.setText("方案未通过 B3 final，不能进入正式播放。")
        self.current_frame_pixmap = None
        self.image_label.setPixmap(QPixmap())
        self.diagnostic_list.clear()
        if exc.audit_result is not None:
            for error in exc.audit_result.errors:
                self.diagnostic_list.addItem(f"ERROR: {error}")
            for warning in exc.audit_result.warnings:
                self.diagnostic_list.addItem(f"WARNING: {warning}")

    def _set_warning_status(self) -> None:
        if self.bundle is None:
            return
        if self.bundle.formal_result:
            self.warning_label.setText(
                f"正式方案：{self.bundle.plan.plan_id} | commit {self.bundle.data_version.git_commit[:12]}"
            )
            self.warning_label.setStyleSheet("padding: 8px; background: #e7f6e7; color: #135c13;")
        else:
            self.warning_label.setText("CONTRACT MISMATCH: 调试候选，不得用于正式报告。")
            self.warning_label.setStyleSheet("padding: 8px; background: #ffe1e1; color: #8a0000; font-weight: bold;")

    def _export_animation(self, kind: str) -> None:
        if self.bundle is None:
            return
        suffix = "gif" if kind == "gif" else "mp4"
        path, _ = QFileDialog.getSaveFileName(
            self,
            f"导出 {suffix.upper()}",
            f"route-animation.{suffix}",
            f"{suffix.upper()} (*.{suffix})",
        )
        if not path:
            return
        options = RenderOptions(visible_route_ids=self.visible_route_ids())
        if kind == "gif":
            export_animation_gif(self.bundle.timeline, self._road_network(), self.bundle.layout, path, options=options)
        else:
            export_animation_mp4(self.bundle.timeline, self._road_network(), self.bundle.layout, path, options=options)
        QMessageBox.information(self, "导出完成", f"已导出：{path}")

    def _export_package(self) -> None:
        if self.route_plan_path is None:
            return
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if not path:
            return
        result = export_route_animation_package(self.route_plan_path, Path(path), render_frames=True)
        QMessageBox.information(self, "导出完成", f"已导出 {len(result.files)} 个文件到：{path}")

    def _append_log(self, message: str) -> None:
        self.solve_log.append(message)


def _double_spin(minimum: float, maximum: float, value: float, suffix: str) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(minimum, maximum)
    spin.setDecimals(2)
    spin.setSingleStep(0.5)
    spin.setValue(value)
    spin.setSuffix(suffix)
    return spin


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    return value


def _safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value)


def main(argv: Optional[list[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    app = QApplication.instance() or QApplication(["mm-final-b8c-gui"])
    route_plan_path = Path(args[0]) if args else None
    window = RouteAnimationWindow(route_plan_path)
    window.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
