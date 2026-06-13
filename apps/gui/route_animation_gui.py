"""B8 PySide6/Qt 路线动画播放器。"""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import time
from typing import Optional

from mm_final.visualization import (
    RenderOptions,
    export_animation_gif,
    export_animation_mp4,
    render_snapshot_png,
)
from mm_final.visualization.exports import RouteAnimationBundle, VisualizationInputError, export_route_animation_package


def _import_qt():
    try:
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtGui import QPixmap
        from PySide6.QtWidgets import (
            QApplication,
            QCheckBox,
            QDoubleSpinBox,
            QFileDialog,
            QFrame,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QListWidget,
            QMainWindow,
            QMessageBox,
            QPushButton,
            QScrollArea,
            QSlider,
            QVBoxLayout,
            QWidget,
        )
    except ImportError as exc:  # pragma: no cover - 由 gui extra 提供
        raise ImportError("PySide6 is required for the B8 GUI. Install the 'gui' extra.") from exc
    return {
        "Qt": Qt,
        "QTimer": QTimer,
        "QPixmap": QPixmap,
        "QApplication": QApplication,
        "QCheckBox": QCheckBox,
        "QDoubleSpinBox": QDoubleSpinBox,
        "QFileDialog": QFileDialog,
        "QFrame": QFrame,
        "QHBoxLayout": QHBoxLayout,
        "QLabel": QLabel,
        "QLineEdit": QLineEdit,
        "QListWidget": QListWidget,
        "QMainWindow": QMainWindow,
        "QMessageBox": QMessageBox,
        "QPushButton": QPushButton,
        "QScrollArea": QScrollArea,
        "QSlider": QSlider,
        "QVBoxLayout": QVBoxLayout,
        "QWidget": QWidget,
    }


qt = _import_qt()
Qt = qt["Qt"]
QTimer = qt["QTimer"]
QPixmap = qt["QPixmap"]
QApplication = qt["QApplication"]
QCheckBox = qt["QCheckBox"]
QDoubleSpinBox = qt["QDoubleSpinBox"]
QFileDialog = qt["QFileDialog"]
QFrame = qt["QFrame"]
QHBoxLayout = qt["QHBoxLayout"]
QLabel = qt["QLabel"]
QLineEdit = qt["QLineEdit"]
QListWidget = qt["QListWidget"]
QMainWindow = qt["QMainWindow"]
QMessageBox = qt["QMessageBox"]
QPushButton = qt["QPushButton"]
QScrollArea = qt["QScrollArea"]
QSlider = qt["QSlider"]
QVBoxLayout = qt["QVBoxLayout"]
QWidget = qt["QWidget"]


class RouteAnimationWindow(QMainWindow):
    """B8b 路线动画播放器窗口。"""

    slider_scale = 1000

    def __init__(self, route_plan_path: Optional[Path] = None):
        super().__init__()
        self.setWindowTitle("B8 Route Animation Player")
        self.resize(1200, 820)

        self.bundle: Optional[RouteAnimationBundle] = None
        self.road_network = None
        self.route_plan_path: Optional[Path] = None
        self.temp_dir = tempfile.TemporaryDirectory(prefix="mm-final-b8-gui-")
        self.current_time_hour = 0.0
        self.playback_model_hours_per_second = 1.0
        self._last_tick = time.monotonic()
        self._syncing_slider = False
        self.route_checkboxes: dict[str, QCheckBox] = {}

        self._build_ui()
        self.timer = QTimer(self)
        self.timer.setInterval(150)
        self.timer.timeout.connect(self._advance_playback)

        if route_plan_path is not None:
            self.load_route_plan(route_plan_path)

    def closeEvent(self, event):  # noqa: N802 - Qt 命名约定
        self.temp_dir.cleanup()
        super().closeEvent(event)

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)

        self.warning_label = QLabel("未加载路线方案")
        self.warning_label.setFrameShape(QFrame.Shape.Panel)
        self.warning_label.setStyleSheet("padding: 8px; background: #fff4ce; color: #4f3b00;")
        root.addWidget(self.warning_label)

        file_row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("选择 RoutePlan JSON")
        browse_button = QPushButton("加载")
        browse_button.clicked.connect(self._browse_route_plan)
        file_row.addWidget(self.path_edit, 1)
        file_row.addWidget(browse_button)
        root.addLayout(file_row)

        body = QHBoxLayout()
        image_panel = QVBoxLayout()
        self.image_label = QLabel("加载合法 RoutePlan 后显示动画帧")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(760, 520)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.image_label)
        image_panel.addWidget(scroll, 1)

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
        side_panel.addWidget(QLabel("路线显隐"))
        self.route_list_widget = QWidget()
        self.route_list_layout = QVBoxLayout(self.route_list_widget)
        self.route_list_layout.addStretch(1)
        side_panel.addWidget(self.route_list_widget)
        side_panel.addWidget(QLabel("审计诊断"))
        self.diagnostic_list = QListWidget()
        side_panel.addWidget(self.diagnostic_list, 1)

        body.addLayout(image_panel, 4)
        body.addLayout(side_panel, 1)
        root.addLayout(body, 1)
        self.setCentralWidget(central)

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
        self._last_tick = now
        speed = float(self.speed_spin.value())
        self.set_time_hour(self.current_time_hour + elapsed_second * self.playback_model_hours_per_second * speed)
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
        self.image_label.setPixmap(pixmap)
        self.image_label.resize(pixmap.size())

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
        path, _ = QFileDialog.getSaveFileName(self, f"导出 {suffix.upper()}", f"route-animation.{suffix}", f"{suffix.upper()} (*.{suffix})")
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


def main(argv: Optional[list[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    app = QApplication.instance() or QApplication(["mm-final-b8-gui"])
    route_plan_path = Path(args[0]) if args else None
    window = RouteAnimationWindow(route_plan_path)
    window.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
