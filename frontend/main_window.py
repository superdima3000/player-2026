import threading
import soundfile as sf
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QFileDialog
)

from backend.equalizer import Equalizer
from backend.effects import EffectsChain
from backend.player import AudioPlayer

from frontend.windows.about_window import AboutWindow
from frontend.windows.eq_window import EQWindow
from frontend.windows.chorus_window import ChorusWindow
from frontend.windows.vibrato_window import VibratoWindow
from frontend.windows.spectrogram_window import SpectrogramWindow
from frontend.windows.filter_settings_window import FilterSettingsWindow

from pathlib import Path

BASE_DIR = Path(__file__).parent


class MainWindow(QMainWindow):
    _playback_finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cool Skeleton EQ 4")
        self.setWindowIcon(QIcon(str(BASE_DIR / "assets" / "logo.jpg")))
        self.setMinimumWidth(500)

        self._player: AudioPlayer | None = None
        self._play_thread: threading.Thread | None = None
        self._is_playing = False
        self._audio_file: str | None = None
        self._duration_sec: float = 0.0
        self._elapsed_sec: float = 0.0

        self._windows: dict = {}
        self._eq_gains: list[float] = [0.0] * 8

        self._vibrato_enabled: bool = False
        self._vibrato_depth: float = 5.0
        self._vibrato_rate: float = 5.0

        self._chorus_enabled: bool = False
        self._chorus_depth: float = 10.0
        self._chorus_rate: float = 1.5
        self._chorus_mix: float = 0.5
        self._chorus_voices: int = 3

        self._paused_frame: int = 0
        self._is_pausing: bool = False
        self._samplerate: int = 44100

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
        self._build_menu()

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

    def _build_menu(self):
        menubar = self.menuBar()

        # File
        file_menu = menubar.addMenu("File")
        file_menu.addAction("About", self._open_window("about"))
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)

        # Tools
        tools_menu = menubar.addMenu("Tools")
        tools_menu.addAction("EQ", self._open_window("eq"))
        tools_menu.addAction("Chorus", self._open_window("chorus"))
        tools_menu.addAction("Vibrato", self._open_window("vibrato"))

        # Visual
        visual_menu = menubar.addMenu("Visual")
        visual_menu.addAction("Spectrogram", self._open_window("spectrogram"))

        # Advanced
        advanced_menu = menubar.addMenu("Advanced")
        advanced_menu.addAction("Filter Settings", self._open_window("filter_settings"))

    def _open_window(self, key: str):
        """Фабрика — возвращает lambda для открытия нужного окна."""

        def _open():
            if key in self._windows and self._windows[key].isVisible():
                self._windows[key].raise_()
                self._windows[key].activateWindow()
                return
            window_map = {
                "about": AboutWindow,
                "eq": EQWindow,
                "chorus": ChorusWindow,
                "vibrato": VibratoWindow,
                "spectrogram": SpectrogramWindow,
                "filter_settings": FilterSettingsWindow,
            }
            self._windows[key] = window_map[key](self)
            self._windows[key].show()

        return _open

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

        with sf.SoundFile(self._audio_file) as f:
            self._samplerate = f.samplerate

        eq = Equalizer(use_fir=True, fs=44100)

        fx = EffectsChain(fs=self._samplerate)
        fx.vibrato_enabled = self._vibrato_enabled
        fx.vibrato.depth_ms = self._vibrato_depth
        fx.vibrato.rate_hz = self._vibrato_rate

        fx.chorus_enabled = self._chorus_enabled
        fx.chorus.depth_ms = self._chorus_depth
        fx.chorus.rate_hz = self._chorus_rate
        fx.chorus.mix = self._chorus_mix
        fx.chorus.voices = self._chorus_voices

        self._player = AudioPlayer(
            audio_file=self._audio_file,
            buffer_size=1,
            block_size=8192,
            use_dual_thread=True,
            equalizer=eq,
            effects_chain=fx,
            start_frame=self._paused_frame
        )

        spec = self._windows.get("spectrogram")
        if spec and spec.isVisible():
            self._player.on_block = spec.push_block

        # play() блокирует — запускаем в отдельном потоке
        self._play_thread = threading.Thread(
            target=self._play_worker, daemon=True
        )
        self._play_thread.start()
        self._paused_frame = 0
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
            self._is_pausing = True
            self._paused_frame = self._player.current_frame
            self._player.stop()
        self._is_playing = False
        self._btn_play.setText("▶ Играть")
        self._timer.stop()

    def _stop(self):
        self._is_pausing = False
        if self._player:
            self._player.stop()
        self._is_playing = False
        self._paused_frame = 0
        self._elapsed_sec = 0.0
        self._btn_play.setText("▶ Играть")
        self._timer.stop()
        self._elapsed_sec = 0.0
        self._time_elapsed.setText("0:00")
        self._progress.setValue(0)

    def _on_playback_finished(self):
        """Вызывается когда файл воспроизведён до конца."""
        if self._is_pausing:
            self._is_pausing = False
            return
        self._is_playing = False
        self._btn_play.setText("▶ Играть")
        self._timer.stop()
        self._progress.setValue(1000)
        self._time_elapsed.setText(self._fmt(self._duration_sec))

    def _tick(self):
        """Каждые 500 мс обновляем прогресс-бар."""
        if not self._is_playing or self._player is None:
            return
            # Берём реальную позицию из плеера, а не накапливаем таймером
        self._elapsed_sec = self._player.current_frame / self._samplerate
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