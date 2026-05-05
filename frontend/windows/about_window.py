from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


class AboutWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About")
        self.setFixedSize(300, 200)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)

        # Картинка
        img_label = QLabel()
        pixmap = QPixmap(str(BASE_DIR / "assets" / "logo.jpg"))
        img_label.setPixmap(pixmap.scaled(
            100, 100,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        ))
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(img_label)

        # Текст
        text = QLabel("Cool Skeleton EQ 4\nАудиоплеер с эквалайзером\n\nВерсия 1.0")
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(text)