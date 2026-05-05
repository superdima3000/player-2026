from PyQt6.QtWidgets import QDialog, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtWidgets import QWidget
import numpy as np


class SpectrogramCanvas(QWidget):
    """Виджет отрисовки спектра."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(660, 300)
        self._magnitudes = np.zeros(512)   # половина FFT

    def update_spectrum(self, magnitudes: np.ndarray):
        self._magnitudes = magnitudes
        self.update()   # триггерим перерисовку

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(15, 15, 20))

        w = self.width()
        h = self.height()
        n = len(self._magnitudes)
        if n == 0:
            return

        bar_w = max(1, w // n)

        for i, mag in enumerate(self._magnitudes):
            # mag уже в дБ, нормализуем 0–1
            norm = np.clip(mag, 0.0, 1.0)
            bar_h = int(norm * h)

            # Цвет: зелёный → жёлтый → красный
            r = int(255 * norm)
            g = int(255 * (1.0 - norm * 0.7))
            b = 60
            color = QColor(r, g, b)

            x = i * bar_w
            painter.fillRect(x, h - bar_h, bar_w - 1, bar_h, color)

        # Оси частот
        painter.setPen(QPen(QColor(100, 100, 100)))
        for label, freq in [("20", 20), ("100", 100), ("1k", 1000),
                             ("5k", 5000), ("10k", 10000), ("20k", 20000)]:
            x = int(freq / 22050 * w)
            painter.drawLine(x, 0, x, h)
            painter.drawText(x + 2, h - 4, label)


class SpectrogramWindow(QDialog):
    FFT_SIZE = 1024

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Spectrogram")
        self.setFixedSize(700, 380)

        self._main = parent
        self._buffer = np.zeros(self.FFT_SIZE, dtype=np.float32)
        self._samplerate = 44100

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        self._canvas = SpectrogramCanvas()
        layout.addWidget(self._canvas)

        # Таймер перерисовки — 30 FPS
        self._timer = QTimer()
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._redraw)
        self._timer.start()

        self._pending: np.ndarray | None = None

    def push_block(self, block: np.ndarray):
        """Вызывается из аудио-потока — сохраняем блок для перерисовки."""
        print(f"push_block called, block shape: {block.shape}")
        mono = block[:, 0] if block.ndim == 2 else block
        # Накапливаем в кольцевой буфер
        n = len(mono)
        self._buffer = np.roll(self._buffer, -n)
        self._buffer[-n:] = mono[:self.FFT_SIZE] if n >= self.FFT_SIZE else mono
        self._pending = self._buffer.copy()

    def _redraw(self):
        if self._pending is None:
            print("_redraw: pending is None")
            return
        print(f"_redraw: drawing spectrum")
        # FFT
        window = np.hanning(len(self._pending))
        spectrum = np.abs(np.fft.rfft(self._pending * window))
        spectrum = spectrum[:self.FFT_SIZE // 2]

        # В дБ, нормализуем
        spectrum_db = 20 * np.log10(spectrum + 1e-9)
        min_db, max_db = -80.0, 0.0
        normalized = (spectrum_db - min_db) / (max_db - min_db)

        self._canvas.update_spectrum(normalized)
        self._pending = None

    def closeEvent(self, event):
        self._timer.stop()
        # Отписываем плеер
        if self._main and self._main._player:
            self._main._player.on_block = None
        super().closeEvent(event)

    def showEvent(self, event):
        self._timer.start()
        # Подписываем плеер если играет
        if self._main and self._main._player:
            self._main._player.on_block = self.push_block
        super().showEvent(event)