from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QSlider, QPushButton, QDoubleSpinBox
)
from PyQt6.QtCore import Qt
from pathlib import Path

# Полосы из equalizer.py
BANDS = [
    (20,    100),
    (100,   256),
    (256,   568),
    (568,   1192),
    (1192,  2440),
    (2440,  4936),
    (4936,  9928),
    (9928,  20000),
]

GAIN_MIN = -70.0
GAIN_MAX = 5.0


def _band_label(low: int, high: int) -> str:
    """Красивое название полосы: 1k вместо 1000"""
    def fmt(f):
        return f"{f // 1000}k" if f >= 1000 else str(f)
    return f"{fmt(low)}–{fmt(high)}\nГц"


class EQWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Equalizer")
        self.setFixedSize(700, 320)

        # Берём плеер из родительского окна
        self._main = parent

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # --- 8 полос ---
        bands_row = QHBoxLayout()
        bands_row.setSpacing(8)

        self._sliders: list[QSlider] = []
        self._spinboxes: list[QDoubleSpinBox] = []

        for i, (low, high) in enumerate(BANDS):
            col = QVBoxLayout()
            col.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            col.setSpacing(4)

            # Значение дБ — спинбокс сверху
            spinbox = QDoubleSpinBox()
            spinbox.setRange(GAIN_MIN, GAIN_MAX)
            spinbox.setSingleStep(0.5)
            spinbox.setValue(0.0)
            spinbox.setSuffix(" dB")
            spinbox.setFixedWidth(80)
            spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)

            # Вертикальный слайдер
            slider = QSlider(Qt.Orientation.Vertical)
            slider.setRange(int(GAIN_MIN * 10), int(GAIN_MAX * 10))
            slider.setValue(0)
            slider.setFixedHeight(150)
            slider.setTickPosition(QSlider.TickPosition.TicksBothSides)
            slider.setTickInterval(20)  # каждые 2 дБ

            # Подпись полосы снизу
            lbl = QLabel(_band_label(low, high))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("font-size: 10px;")

            # Синхронизация слайдер ↔ спинбокс
            band_idx = i
            slider.valueChanged.connect(
                lambda val, idx=band_idx, sb=spinbox: self._on_slider(idx, val, sb)
            )
            spinbox.valueChanged.connect(
                lambda val, idx=band_idx, sl=slider: self._on_spinbox(idx, val, sl)
            )

            col.addWidget(spinbox)
            col.addWidget(slider, alignment=Qt.AlignmentFlag.AlignHCenter)
            col.addWidget(lbl)

            self._sliders.append(slider)
            self._spinboxes.append(spinbox)
            bands_row.addLayout(col)

        layout.addLayout(bands_row)

        for i, gain in enumerate(self._main._eq_gains):
            self._sliders[i].blockSignals(True)
            self._spinboxes[i].blockSignals(True)
            self._sliders[i].setValue(int(gain * 10))
            self._spinboxes[i].setValue(gain)
            self._sliders[i].blockSignals(False)
            self._spinboxes[i].blockSignals(False)

        # --- Кнопка сброса ---
        btn_reset = QPushButton("Сбросить (0 dB)")
        btn_reset.setFixedWidth(160)
        btn_reset.clicked.connect(self._reset)
        layout.addWidget(btn_reset, alignment=Qt.AlignmentFlag.AlignCenter)

    # ------------------------------------------------------------------

    def _on_slider(self, band: int, raw_val: int, spinbox: QDoubleSpinBox):
        """Слайдер изменился → обновляем спинбокс и плеер."""
        db = raw_val / 10.0
        spinbox.blockSignals(True)
        spinbox.setValue(db)
        spinbox.blockSignals(False)
        self._apply_gain(band, db)

    def _on_spinbox(self, band: int, db: float, slider: QSlider):
        """Спинбокс изменился → обновляем слайдер и плеер."""
        slider.blockSignals(True)
        slider.setValue(int(db * 10))
        slider.blockSignals(False)
        self._apply_gain(band, db)

    def _apply_gain(self, band: int, db: float):
        """Передаём усиление в плеер если он существует."""
        if self._main:
            self._main._eq_gains[band] = db
        if self._main and self._main._player:
            self._main._player.set_gain(band, db)

    def _reset(self):
        for i, (slider, spinbox) in enumerate(zip(self._sliders, self._spinboxes)):
            slider.blockSignals(True)
            spinbox.blockSignals(True)
            slider.setValue(0)
            spinbox.setValue(0.0)
            slider.blockSignals(False)
            spinbox.blockSignals(False)
            self._apply_gain(i, 0.0)