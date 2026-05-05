import threading
import soundfile as sf
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QFileDialog
)

from backend.equalizer import Equalizer
from backend.effects import EffectsChain
from backend.player import AudioPlayer


class MainWindow(QMainWindow):
    _playback_finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Player 2026")
        self.setMinimumWidth(500)

        self._player: AudioPlayer | None = None
        self._play_thread: threading.Thread | None = None
        self._is_playing = False
        self._audio_file: str | None = None
        self._duration_sec: float = 0.0
        self._elapsed_sec: float = 0.0

        self._playback_finished.connect(self._on_playback_finished)

        # Таймер для прогресс-бара (каждые 500 мс)
        self._timer = QTimer()
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._tick)

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # --- Выбор файла ---
        file_row = QHBoxLayout()
        self._file_label = QLabel("Файл не выбран")
        self._file_label.setStyleSheet("color: grey;")
        self._file_label.setWordWrap(True)

        btn_open = QPushButton("📂 Открыть")
        btn_open.setFixedWidth(110)
        btn_open.clicked.connect(self._open_file)

        file_row.addWidget(self._file_label, stretch=1)
        file_row.addWidget(btn_open)
        layout.addLayout(file_row)

        # --- Прогресс ---
        self._progress = QSlider(Qt.Orientation.Horizontal)
        self._progress.setRange(0, 1000)
        self._progress.setValue(0)
        self._progress.setEnabled(False)   # пока только отображение
        layout.addWidget(self._progress)

        time_row = QHBoxLayout()
        self._time_elapsed = QLabel("0:00")
        self._time_total = QLabel("0:00")
        time_row.addWidget(self._time_elapsed)
        time_row.addStretch()
        time_row.addWidget(self._time_total)
        layout.addLayout(time_row)

        # --- Кнопки управления ---
        ctrl_row = QHBoxLayout()
        ctrl_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._btn_play = QPushButton("▶ Играть")
        self._btn_play.setFixedSize(120, 40)
        self._btn_play.setEnabled(False)
        self._btn_play.clicked.connect(self._toggle_play)

        btn_stop = QPushButton("⏹ Стоп")
        btn_stop.setFixedSize(100, 40)
        btn_stop.clicked.connect(self._stop)

        ctrl_row.addWidget(self._btn_play)
        ctrl_row.addSpacing(12)
        ctrl_row.addWidget(btn_stop)
        layout.addLayout(ctrl_row)

        layout.addStretch()

    # ------------------------------------------------------------------
    # Логика
    # ------------------------------------------------------------------

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выбрать аудиофайл", "", "WAV файлы (*.wav)"
        )
        if not path:
            return

        self._audio_file = path
        self._file_label.setText(path.split("/")[-1].split("\\")[-1])
        self._file_label.setStyleSheet("")

        # Читаем длительность
        with sf.SoundFile(path) as f:
            self._duration_sec = len(f) / f.samplerate
        self._time_total.setText(self._fmt(self._duration_sec))
        self._elapsed_sec = 0.0
        self._time_elapsed.setText("0:00")
        self._progress.setValue(0)

        self._btn_play.setEnabled(True)
        self._stop()   # сбрасываем предыдущее воспроизведение если было

    def _toggle_play(self):
        if not self._is_playing:
            self._start_play()
        else:
            self._pause()

    def _start_play(self):
        if not self._audio_file:
            return

        eq = Equalizer(use_fir=True, fs=44100)
        fx = EffectsChain(fs=44100)

        self._player = AudioPlayer(
            audio_file=self._audio_file,
            buffer_size=8192,
            block_size=1024,
            use_dual_thread=True,
            equalizer=eq,
            effects_chain=fx,
        )

        # play() блокирует — запускаем в отдельном потоке
        self._play_thread = threading.Thread(
            target=self._play_worker, daemon=True
        )
        self._play_thread.start()

        self._is_playing = True
        self._btn_play.setText("⏸ Пауза")
        self._timer.start()

    def _play_worker(self):
        """Запускается в отдельном потоке — play() блокирует до конца файла."""
        self._player.play()
        # Файл закончился — обновляем UI из главного потока
        self._playback_finished.emit()

    def _pause(self):
        """Пауза — останавливаем поток воспроизведения."""
        if self._player:
            self._player.stop()
        self._is_playing = False
        self._btn_play.setText("▶ Играть")
        self._timer.stop()

    def _stop(self):
        if self._player:
            self._player.stop()
        self._is_playing = False
        self._btn_play.setText("▶ Играть")
        self._timer.stop()
        self._elapsed_sec = 0.0
        self._time_elapsed.setText("0:00")
        self._progress.setValue(0)

    def _on_playback_finished(self):
        """Вызывается когда файл воспроизведён до конца."""
        self._is_playing = False
        self._btn_play.setText("▶ Играть")
        self._timer.stop()
        self._progress.setValue(1000)
        self._time_elapsed.setText(self._fmt(self._duration_sec))

    def _tick(self):
        """Каждые 500 мс обновляем прогресс-бар."""
        if not self._is_playing:
            return
        self._elapsed_sec += 0.5
        if self._duration_sec > 0:
            pos = int(self._elapsed_sec / self._duration_sec * 1000)
            self._progress.setValue(min(pos, 1000))
        self._time_elapsed.setText(self._fmt(self._elapsed_sec))

    @staticmethod
    def _fmt(sec: float) -> str:
        sec = max(0, int(sec))
        return f"{sec // 60}:{sec % 60:02d}"


# ----------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())