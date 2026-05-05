# frontend/windows/vibrato_window.py

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QSlider, QPushButton, QCheckBox, QDoubleSpinBox
)
from PyQt6.QtCore import Qt


class VibratoWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vibrato")
        self.setFixedSize(350, 220)

        self._main = parent

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # --- Включить/выключить ---
        self._checkbox = QCheckBox("Включить вибрато")
        self._checkbox.setChecked(self._main._vibrato_enabled)
        self._checkbox.toggled.connect(self._on_toggle)
        layout.addWidget(self._checkbox)

        # --- Параметры ---
        grid = QGridLayout()
        grid.setSpacing(8)

        # Depth
        grid.addWidget(QLabel("Глубина (мс):"), 0, 0)
        self._depth_spin = QDoubleSpinBox()
        self._depth_spin.setRange(0.1, 15.0)
        self._depth_spin.setSingleStep(0.1)
        self._depth_spin.setValue(self._main._vibrato_depth)
        self._depth_spin.setSuffix(" мс")
        grid.addWidget(self._depth_spin, 0, 1)

        self._depth_slider = QSlider(Qt.Orientation.Horizontal)
        self._depth_slider.setRange(1, 150)
        self._depth_slider.setValue(int(self._main._vibrato_depth * 10))
        grid.addWidget(self._depth_slider, 0, 2)

        # Rate
        grid.addWidget(QLabel("Частота (Гц):"), 1, 0)
        self._rate_spin = QDoubleSpinBox()
        self._rate_spin.setRange(0.1, 15.0)
        self._rate_spin.setSingleStep(0.1)
        self._rate_spin.setValue(self._main._vibrato_rate)
        self._rate_spin.setSuffix(" Гц")
        grid.addWidget(self._rate_spin, 1, 1)

        self._rate_slider = QSlider(Qt.Orientation.Horizontal)
        self._rate_slider.setRange(1, 150)
        self._rate_slider.setValue(int(self._main._vibrato_rate * 10))
        grid.addWidget(self._rate_slider, 1, 2)

        layout.addLayout(grid)

        # --- Сброс ---
        btn_reset = QPushButton("Сбросить")
        btn_reset.setFixedWidth(120)
        btn_reset.clicked.connect(self._reset)
        layout.addWidget(btn_reset, alignment=Qt.AlignmentFlag.AlignCenter)

        # --- Сигналы ---
        self._depth_slider.valueChanged.connect(
            lambda v: self._on_slider(v, self._depth_spin, "depth")
        )
        self._depth_spin.valueChanged.connect(
            lambda v: self._on_spinbox(v, self._depth_slider, "depth")
        )
        self._rate_slider.valueChanged.connect(
            lambda v: self._on_slider(v, self._rate_spin, "rate")
        )
        self._rate_spin.valueChanged.connect(
            lambda v: self._on_spinbox(v, self._rate_slider, "rate")
        )

    # ------------------------------------------------------------------

    def _on_toggle(self, enabled: bool):
        self._main._vibrato_enabled = enabled
        if self._main._player:
            self._main._player.set_vibrato(enabled)

    def _on_slider(self, raw: int, spinbox: QDoubleSpinBox, param: str):
        val = raw / 10.0
        spinbox.blockSignals(True)
        spinbox.setValue(val)
        spinbox.blockSignals(False)
        self._apply(param, val)

    def _on_spinbox(self, val: float, slider: QSlider, param: str):
        slider.blockSignals(True)
        slider.setValue(int(val * 10))
        slider.blockSignals(False)
        self._apply(param, val)

    def _apply(self, param: str, val: float):
        if param == "depth":
            self._main._vibrato_depth = val
            if self._main._player:
                self._main._player.set_vibrato_depth(val)
        elif param == "rate":
            self._main._vibrato_rate = val
            if self._main._player:
                self._main._player.set_vibrato_rate(val)

    def _reset(self):
        for slider, spin, param, default in [
            (self._depth_slider, self._depth_spin, "depth", 5.0),
            (self._rate_slider,  self._rate_spin,  "rate",  5.0),
        ]:
            slider.blockSignals(True)
            spin.blockSignals(True)
            slider.setValue(int(default * 10))
            spin.setValue(default)
            slider.blockSignals(False)
            spin.blockSignals(False)
            self._apply(param, default)