# frontend/windows/filter_settings_window.py

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QSpinBox, QPushButton, QRadioButton,
    QButtonGroup, QGroupBox
)
from PyQt6.QtCore import Qt


class FilterSettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Filter Settings")
        self.setFixedSize(400, 320)

        self._main = parent
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # --- Тип фильтра ---
        type_group = QGroupBox("Тип фильтра")
        type_layout = QHBoxLayout(type_group)

        self._radio_fir = QRadioButton("КИХ (треугольное окно)")
        self._radio_iir = QRadioButton("БИХ (эллиптический)")
        self._btn_group = QButtonGroup()
        self._btn_group.addButton(self._radio_fir, 0)
        self._btn_group.addButton(self._radio_iir, 1)

        # Восстанавливаем текущий тип
        use_fir = self._main._filter_use_fir if hasattr(self._main, "_filter_use_fir") else True
        self._radio_fir.setChecked(use_fir)
        self._radio_iir.setChecked(not use_fir)

        self._radio_fir.toggled.connect(self._on_type_changed)

        type_layout.addWidget(self._radio_fir)
        type_layout.addWidget(self._radio_iir)
        layout.addWidget(type_group)

        # --- Порядки фильтров ---
        order_group = QGroupBox("Порядок фильтров")
        grid = QGridLayout(order_group)
        grid.setSpacing(8)
        grid.setColumnMinimumWidth(0, 160)

        # Заголовки
        grid.addWidget(QLabel(""), 0, 0)
        grid.addWidget(QLabel("БИХ порядок"), 0, 1, Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(QLabel("КИХ отводы"), 0, 2, Qt.AlignmentFlag.AlignCenter)

        params = [
            ("ФНЧ (полоса 1):",        "lp", 6,    1001),
            ("Полосовой (полосы 2–7):", "bp", 3,    751),
            ("ФВЧ (полоса 8):",         "hp", 6,    501),
        ]

        self._iir_spins: dict[str, QSpinBox] = {}
        self._fir_spins: dict[str, QSpinBox] = {}

        for row, (label, key, iir_def, fir_def) in enumerate(params, start=1):
            grid.addWidget(QLabel(label), row, 0)

            iir_spin = QSpinBox()
            iir_spin.setRange(1, 20)
            iir_spin.setValue(getattr(self._main, f"_iir_order_{key}", iir_def))
            iir_spin.setFixedWidth(80)
            iir_spin.valueChanged.connect(
                lambda v, k=key: self._on_iir_changed(k, v)
            )
            grid.addWidget(iir_spin, row, 1, Qt.AlignmentFlag.AlignCenter)

            fir_spin = QSpinBox()
            fir_spin.setRange(101, 2001)
            fir_spin.setSingleStep(50)
            fir_spin.setValue(getattr(self._main, f"_fir_taps_{key}", fir_def))
            fir_spin.setFixedWidth(80)
            fir_spin.valueChanged.connect(
                lambda v, k=key: self._on_fir_changed(k, v)
            )
            grid.addWidget(fir_spin, row, 2, Qt.AlignmentFlag.AlignCenter)

            self._iir_spins[key] = iir_spin
            self._fir_spins[key] = fir_spin

        layout.addWidget(order_group)

        # --- Сброс ---
        btn_reset = QPushButton("Сбросить по умолчанию")
        btn_reset.setFixedWidth(180)
        btn_reset.clicked.connect(self._reset)
        layout.addWidget(btn_reset, alignment=Qt.AlignmentFlag.AlignCenter)

    # ------------------------------------------------------------------

    def _on_type_changed(self, fir_checked: bool):
        self._main._filter_use_fir = fir_checked
        if self._main._player:
            self._main._player.set_filter_type(fir_checked)

    def _on_iir_changed(self, key: str, value: int):
        setattr(self._main, f"_iir_order_{key}", value)
        if self._main._player:
            getattr(self._main._player, f"set_iir_order_{key}")(value)

    def _on_fir_changed(self, key: str, value: int):
        setattr(self._main, f"_fir_taps_{key}", value)
        if self._main._player:
            getattr(self._main._player, f"set_fir_taps_{key}")(value)

    def _reset(self):
        defaults = {
            "lp": (6, 1001),
            "bp": (3, 751),
            "hp": (6, 501),
        }
        for key, (iir_def, fir_def) in defaults.items():
            self._iir_spins[key].setValue(iir_def)
            self._fir_spins[key].setValue(fir_def)

        self._radio_fir.setChecked(True)