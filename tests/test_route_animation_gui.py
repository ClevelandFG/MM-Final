import os
from pathlib import Path

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from apps.gui.route_animation_gui import RouteAnimationWindow  # noqa: E402


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "route_plans"


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication(["pytest-b8-gui"])
    return app


def test_route_animation_gui_loads_scrubs_renders_and_toggles_routes(qt_app):
    window = RouteAnimationWindow()
    try:
        loaded = window.load_route_plan(FIXTURE_DIR / "full-coverage-smoke-001.json")

        assert loaded is True
        assert window.bundle is not None
        assert window.route_checkboxes
        assert window.time_slider.maximum() == window.slider_scale

        completion = window.bundle.timeline.completion_time_hour
        window.set_time_hour(completion / 2)

        assert window.current_time_hour == pytest.approx(completion / 2)
        assert f"/ {completion:.2f} h" in window.time_label.text()
        pixmap = window.image_label.pixmap()
        assert pixmap is not None
        assert not pixmap.isNull()

        first_route_id, checkbox = next(iter(window.route_checkboxes.items()))
        checkbox.setChecked(False)

        assert first_route_id not in window.visible_route_ids()
    finally:
        window.close()
