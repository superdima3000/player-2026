import queue
import sys
import threading

import numpy as np
import sounddevice as sd
import soundfile as sf

from filters import EllipticIIRFilter, TriangularFIRFilter


class DualThreadAudioBuffer:
    """
    Двухпоточный буфер воспроизведения с опциональным фильтром на выходе.

    Поток-продюсер читает файл и кладёт блоки в queue.Queue.
    Callback sounddevice забирает блоки, фильтрует и передаёт звуковой карте.

    Схема обработки:
        [Поток 1] файл → queue.put()
        [Поток 2] queue.get() → filter.process() → звуковая карта

    Parameters
    ----------
    audio_file : str
        Путь к WAV-файлу.
    buffer_size : int
        Максимальное число блоков в очереди.
    block_size : int
        Число сэмплов в одном блоке (рекомендуется 512–4096).
    filter : EllipticIIRFilter | TriangularFIRFilter | None
        Фильтр, применяемый к каждому блоку перед выводом.
        None — воспроизведение без фильтрации.
    """

    def __init__(
        self,
        audio_file: str,
        buffer_size: int = 8192,
        block_size: int = 1024,
        filter: "EllipticIIRFilter | TriangularFIRFilter | None" = None,
    ):
        self.audio_file = audio_file
        self.buffer_size = buffer_size
        self.block_size = block_size
        self.filter = filter

        self._ring_buffer: queue.Queue = queue.Queue(maxsize=buffer_size)
        self._underrun_count = 0
        self._stop_event = threading.Event()
        self._producer_thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _producer(self) -> None:
        """Поток 1: читает файл → кладёт блоки в очередь."""
        try:
            with sf.SoundFile(self.audio_file) as f:
                while not self._stop_event.is_set():
                    block = f.read(self.block_size, dtype="float32", always_2d=True)
                    if len(block) == 0:
                        break
                    self._ring_buffer.put(block)  # блокируется если очередь полна
        finally:
            self._stop_event.set()

    def _callback(self, outdata, frames, time, status) -> None:
        """Поток 2: забирает блок → фильтрует → отдаёт звуковой карте."""
        try:
            data = self._ring_buffer.get_nowait()

            # Фильтрация блока
            if self.filter is not None:
                data = self.filter.process(data, stateful=True).astype(np.float32)

            if len(data) < len(outdata):
                outdata[: len(data)] = data
                outdata[len(data) :] = 0
                raise sd.CallbackStop
            outdata[:] = data
        except queue.Empty:
            self._underrun_count += 1
            print(f"⚠ Underrun #{self._underrun_count}!", file=sys.stderr)
            outdata.fill(0)
            if self._stop_event.is_set():
                raise sd.CallbackStop

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def underrun_count(self) -> int:
        return self._underrun_count

    def play(self) -> None:
        """Запускает воспроизведение, блокирует до конца файла."""
        self._ring_buffer = queue.Queue(maxsize=self.buffer_size)
        self._stop_event = threading.Event()
        self._underrun_count = 0
        if self.filter is not None:
            self.filter.reset()

        with sf.SoundFile(self.audio_file) as f:
            samplerate = f.samplerate
            channels = f.channels

        self._producer_thread = threading.Thread(target=self._producer, daemon=True)
        self._producer_thread.start()

        with sd.OutputStream(
            samplerate=samplerate,
            channels=channels,
            blocksize=self.block_size,
            dtype="float32",
            callback=self._callback,
        ):
            label = type(self.filter).__name__ if self.filter else "без фильтра"
            print(f"▶ Двухпоточный [{label}] | BUFFER_SIZE={self.buffer_size}")
            self._stop_event.wait()
            self._producer_thread.join()

        print(f"✅ Готово. Underrun: {self._underrun_count}")


# ----------------------------------------------------------------------
# Точка входа
# ----------------------------------------------------------------------

if __name__ == "__main__":
    iir = EllipticIIRFilter(order=2, rp=1.0, rs=70.0, cutoff=100, btype="lowpass", fs=48_000)
    fir = TriangularFIRFilter(btype="lowpass", numtaps=1000, cutoff=100, fs=48_000)

    DualThreadAudioBuffer("input.wav", buffer_size=1,
                           block_size=8128, filter=iir).play()