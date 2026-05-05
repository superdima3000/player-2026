from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt


class FilterSettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Filter Settings")
        self.setFixedSize(400, 300)

        layout = QVBoxLayout(self)
        label = QLabel("🚧 Настройки фильтров — в разработке")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)