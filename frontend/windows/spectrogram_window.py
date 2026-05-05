from PyQt6.QtWidgets import QDialog, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtWidgets import QWidget
import numpy as np


class SpectrogramCanvas(QWidget):
    """Виджет отрисовки спектра с логарифмической шкалой частот."""

    FS = 44100
    FFT_SIZE = 1024

    N_BARS = 128          # было 64, стало больше
    FREQ_MIN = 20.0
    FREQ_MAX = 20000.0

    DB_MIN = -70.0
    DB_MAX = 10.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(660, 300)
        self._magnitudes = np.zeros(self.N_BARS, dtype=np.float32)
        self._precompute_bins()

    def _precompute_bins(self):
        freqs = np.fft.rfftfreq(self.FFT_SIZE, d=1.0 / self.FS)

        log_edges = np.logspace(
            np.log10(self.FREQ_MIN),
            np.log10(self.FREQ_MAX),
            self.N_BARS + 1
        )

        self._bin_ranges = []
        for i in range(self.N_BARS):
            lo, hi = log_edges[i], log_edges[i + 1]
            idx = np.where((freqs >= lo) & (freqs < hi))[0]
            self._bin_ranges.append(idx)

    def update_spectrum(self, raw_spectrum: np.ndarray):
        """
        raw_spectrum: линейный спектр амплитуд, shape ~ (FFT_SIZE//2 + 1,)
        """
        raw_spectrum = np.asarray(raw_spectrum, dtype=np.float32)

        bars_db = np.full(self.N_BARS, self.DB_MIN, dtype=np.float32)

        for i, idx in enumerate(self._bin_ranges):
            if idx.size == 0:
                continue

            # Берём средний уровень в полосе, но лучше чуть устойчивее — максимум или среднеквадратичное.
            # Для визуализации обычно RMS/mean ок, но максимум даёт более "живую" картинку.
            band = raw_spectrum[idx]
            amp = np.sqrt(np.mean(np.square(band)) + 1e-20)

            bars_db[i] = 20.0 * np.log10(amp + 1e-12)

        self._magnitudes = np.clip(
            (bars_db - self.DB_MIN) / (self.DB_MAX - self.DB_MIN),
            0.0,
            1.0
        ).astype(np.float32)

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(self.rect(), QColor(15, 15, 20))

        w = self.width()
        h = self.height()
        n = len(self._magnitudes)
        if n == 0:
            return

        bottom_pad = 20
        gap = 1
        usable_w = w - gap * (n - 1)
        bar_w = max(1, usable_w // n)

        for i, norm in enumerate(self._magnitudes):
            bar_h = int(norm * (h - bottom_pad))
            if bar_h <= 0:
                continue

            # Цвет: синий -> зелёный -> жёлтый -> красный
            if norm < 0.33:
                t = norm / 0.33
                r = 0
                g = int(180 * t)
                b = int(255 - 120 * t)
            elif norm < 0.66:
                t = (norm - 0.33) / 0.33
                r = int(255 * t * 0.7)
                g = int(180 + 75 * t)
                b = 0
            else:
                t = (norm - 0.66) / 0.34
                r = int(180 + 75 * t)
                g = int(255 - 200 * t)
                b = 0

            x = i * (bar_w + gap)
            painter.fillRect(x, h - bottom_pad - bar_h, bar_w, bar_h, QColor(r, g, b))

        painter.setPen(QPen(QColor(160, 160, 160)))

        labels = [
            ("20", 20), ("50", 50), ("100", 100), ("200", 200),
            ("500", 500), ("1k", 1000), ("2k", 2000), ("5k", 5000),
            ("10k", 10000), ("20k", 20000)
        ]

        for label, freq in labels:
            if freq < self.FREQ_MIN or freq > self.FREQ_MAX:
                continue

            log_pos = (
                np.log10(freq) - np.log10(self.FREQ_MIN)
            ) / (
                np.log10(self.FREQ_MAX) - np.log10(self.FREQ_MIN)
            )

            x = int(log_pos * (w - 1))
            painter.drawLine(x, 0, x, h - bottom_pad)
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
        mono = block[:, 0] if block.ndim == 2 else block
        # Накапливаем в кольцевой буфер
        n = len(mono)
        self._buffer = np.roll(self._buffer, -n)
        self._buffer[-n:] = mono[:self.FFT_SIZE] if n >= self.FFT_SIZE else mono
        self._pending = self._buffer.copy()

    def _redraw(self):
        if self._pending is None:
            return

        x = np.asarray(self._pending, dtype=np.float32)
        n = len(x)

        window = np.hanning(n)
        xw = x * window

        spectrum = np.abs(np.fft.rfft(xw))

        # Компенсация окна по амплитуде:
        # для Hann окна обычно используют деление на sum(window)/2 или эквивалентную нормализацию
        spectrum = spectrum / (np.sum(window) / 2.0 + 1e-12)

        # Перевод в dB относительно полной шкалы
        spectrum_db = 20.0 * np.log10(np.maximum(spectrum, 1e-12))

        min_db, max_db = -70.0, 10.0
        normalized = np.clip((spectrum_db - min_db) / (max_db - min_db), 0.0, 1.0)

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
        if self._main and self._main._player:
            self._main._player.on_block = self.push_block
            print(f"showEvent: subscribed to player {self._main._player}")
        else:
            print(f"showEvent: no player, _main={self._main}, _player={self._main._player if self._main else None}")
        super().showEvent(event)