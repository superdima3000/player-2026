# frontend/windows/chorus_window.py

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout,
    QLabel, QSlider, QPushButton, QCheckBox,
    QDoubleSpinBox, QSpinBox
)
from PyQt6.QtCore import Qt


class ChorusWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chorus")
        self.setFixedSize(380, 280)

        self._main = parent

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # --- Включить/выключить ---
        self._checkbox = QCheckBox("Включить хор")
        self._checkbox.setChecked(self._main._chorus_enabled)
        self._checkbox.toggled.connect(self._on_toggle)
        layout.addWidget(self._checkbox)

        # --- Параметры ---
        grid = QGridLayout()
        grid.setSpacing(8)
        grid.setColumnMinimumWidth(0, 110)

        # Depth
        grid.addWidget(QLabel("Глубина (мс):"), 0, 0)
        self._depth_spin = QDoubleSpinBox()
        self._depth_spin.setRange(0.1, 30.0)
        self._depth_spin.setSingleStep(0.5)
        self._depth_spin.setValue(self._main._chorus_depth)
        self._depth_spin.setSuffix(" мс")
        self._depth_spin.setFixedWidth(85)
        grid.addWidget(self._depth_spin, 0, 1)

        self._depth_slider = QSlider(Qt.Orientation.Horizontal)
        self._depth_slider.setRange(1, 300)
        self._depth_slider.setValue(int(self._main._chorus_depth * 10))
        grid.addWidget(self._depth_slider, 0, 2)

        # Rate
        grid.addWidget(QLabel("Частота (Гц):"), 1, 0)
        self._rate_spin = QDoubleSpinBox()
        self._rate_spin.setRange(0.1, 10.0)
        self._rate_spin.setSingleStep(0.1)
        self._rate_spin.setValue(self._main._chorus_rate)
        self._rate_spin.setSuffix(" Гц")
        self._rate_spin.setFixedWidth(85)
        grid.addWidget(self._rate_spin, 1, 1)

        self._rate_slider = QSlider(Qt.Orientation.Horizontal)
        self._rate_slider.setRange(1, 100)
        self._rate_slider.setValue(int(self._main._chorus_rate * 10))
        grid.addWidget(self._rate_slider, 1, 2)

        # Mix
        grid.addWidget(QLabel("Mix (dry/wet):"), 2, 0)
        self._mix_spin = QDoubleSpinBox()
        self._mix_spin.setRange(0.0, 1.0)
        self._mix_spin.setSingleStep(0.05)
        self._mix_spin.setValue(self._main._chorus_mix)
        self._mix_spin.setFixedWidth(85)
        grid.addWidget(self._mix_spin, 2, 1)

        self._mix_slider = QSlider(Qt.Orientation.Horizontal)
        self._mix_slider.setRange(0, 100)
        self._mix_slider.setValue(int(self._main._chorus_mix * 100))
        grid.addWidget(self._mix_slider, 2, 2)

        # Voices
        grid.addWidget(QLabel("Голоса:"), 3, 0)
        self._voices_spin = QSpinBox()
        self._voices_spin.setRange(2, 6)
        self._voices_spin.setValue(self._main._chorus_voices)
        self._voices_spin.setFixedWidth(85)
        grid.addWidget(self._voices_spin, 3, 1)

        self._voices_slider = QSlider(Qt.Orientation.Horizontal)
        self._voices_slider.setRange(2, 6)
        self._voices_slider.setValue(self._main._chorus_voices)
        grid.addWidget(self._voices_slider, 3, 2)

        layout.addLayout(grid)

        # --- Сброс ---
        btn_reset = QPushButton("Сбросить")
        btn_reset.setFixedWidth(120)
        btn_reset.clicked.connect(self._reset)
        layout.addWidget(btn_reset, alignment=Qt.AlignmentFlag.AlignCenter)

        # --- Сигналы ---
        self._depth_slider.valueChanged.connect(
            lambda v: self._on_slider_f(v, self._depth_spin, "depth", 10.0))
        self._depth_spin.valueChanged.connect(
            lambda v: self._on_spinbox_f(v, self._depth_slider, "depth", 10.0))

        self._rate_slider.valueChanged.connect(
            lambda v: self._on_slider_f(v, self._rate_spin, "rate", 10.0))
        self._rate_spin.valueChanged.connect(
            lambda v: self._on_spinbox_f(v, self._rate_slider, "rate", 10.0))

        self._mix_slider.valueChanged.connect(
            lambda v: self._on_slider_f(v, self._mix_spin, "mix", 100.0))
        self._mix_spin.valueChanged.connect(
            lambda v: self._on_spinbox_f(v, self._mix_slider, "mix", 100.0))

        self._voices_slider.valueChanged.connect(
            lambda v: self._on_slider_i(v, self._voices_spin, "voices"))
        self._voices_spin.valueChanged.connect(
            lambda v: self._on_spinbox_i(v, self._voices_slider, "voices"))

    # ------------------------------------------------------------------

    def _on_toggle(self, enabled: bool):
        self._main._chorus_enabled = enabled
        if self._main._player:
            self._main._player.set_chorus(enabled)

    def _on_slider_f(self, raw: int, spin: QDoubleSpinBox, param: str, scale: float):
        val = raw / scale
        spin.blockSignals(True)
        spin.setValue(val)
        spin.blockSignals(False)
        self._apply(param, val)

    def _on_spinbox_f(self, val: float, slider: QSlider, param: str, scale: float):
        slider.blockSignals(True)
        slider.setValue(int(val * scale))
        slider.blockSignals(False)
        self._apply(param, val)

    def _on_slider_i(self, val: int, spin: QSpinBox, param: str):
        spin.blockSignals(True)
        spin.setValue(val)
        spin.blockSignals(False)
        self._apply(param, val)

    def _on_spinbox_i(self, val: int, slider: QSlider, param: str):
        slider.blockSignals(True)
        slider.setValue(val)
        slider.blockSignals(False)
        self._apply(param, val)

    def _apply(self, param: str, val):
        dispatch = {
            "depth":  (lambda v: setattr(self._main, "_chorus_depth",  v),
                       lambda v: self._main._player.set_chorus_depth(v)),
            "rate":   (lambda v: setattr(self._main, "_chorus_rate",   v),
                       lambda v: self._main._player.set_chorus_rate(v)),
            "mix":    (lambda v: setattr(self._main, "_chorus_mix",    v),
                       lambda v: self._main._player.set_chorus_mix(v)),
            "voices": (lambda v: setattr(self._main, "_chorus_voices", v),
                       lambda v: self._main._player.set_chorus_voices(v)),
        }
        save_fn, player_fn = dispatch[param]
        save_fn(val)
        if self._main._player:
            player_fn(val)

    def _reset(self):
        defaults = [
            (self._depth_slider,  self._depth_spin,  "depth",  10.0,  10.0),
            (self._rate_slider,   self._rate_spin,   "rate",   1.5,   10.0),
            (self._mix_slider,    self._mix_spin,    "mix",    0.5,   100.0),
        ]
        for slider, spin, param, default, scale in defaults:
            slider.blockSignals(True)
            spin.blockSignals(True)
            slider.setValue(int(default * scale))
            spin.setValue(default)
            slider.blockSignals(False)
            spin.blockSignals(False)
            self._apply(param, default)

        # Voices отдельно (int)
        self._voices_slider.blockSignals(True)
        self._voices_spin.blockSignals(True)
        self._voices_slider.setValue(3)
        self._voices_spin.setValue(3)
        self._voices_slider.blockSignals(False)
        self._voices_spin.blockSignals(False)
        self._apply("voices", 3)