import collections
import sys

import numpy as np
import sounddevice as sd
import soundfile as sf

from backend.filters import EllipticIIRFilter, TriangularFIRFilter


class SingleThreadAudioBuffer:
    """
    Однопоточный буфер воспроизведения с опциональным фильтром на выходе.

    Все действия (чтение файла, заполнение буфера, фильтрация, вывод)
    происходят внутри callback sounddevice — в одном потоке.

    Схема обработки:
        файл → _fill_buffer() → deque → filter.process() → звуковая карта

    Parameters
    ----------
    audio_file : str
        Путь к WAV-файлу.
    buffer_size : int
        Максимальное число блоков в deque.
    block_size : int
        Число сэмплов в одном блоке (рекомендуется 512–4096).
    filter : EllipticIIRFilter | TriangularFIRFilter | None
        Фильтр, применяемый к каждому блоку перед выводом.
        None — воспроизведение без фильтрации.
    """

    def __init__(
        self,
        audio_file: str,
        buffer_size: int = 64,
        block_size: int = 1024,
        filter: "EllipticIIRFilter | TriangularFIRFilter | None" = None,
    ):
        self.audio_file = audio_file
        self.buffer_size = buffer_size
        self.block_size = block_size
        self.filter = filter

        self._buffer: collections.deque = collections.deque()
        self._underrun_count = 0
        self._sf: sf.SoundFile | None = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _fill_buffer(self) -> None:
        """Читает из файла блоки до заполнения deque."""
        while self._sf and len(self._buffer) < self.buffer_size:
            block = self._sf.read(self.block_size, dtype="float32", always_2d=True)
            if len(block) == 0:
                self._sf.close()
                self._sf = None
                break
            self._buffer.append(block)

    def _callback(self, outdata, frames, time, status) -> None:
        # 1. Пополнить буфер из файла
        self._fill_buffer()

        if self._buffer:
            data = self._buffer.popleft()

            # 2. Фильтрация блока
            if self.filter is not None:
                data = self.filter.process(data, stateful=True).astype(np.float32)

            if len(data) < len(outdata):
                outdata[: len(data)] = data
                outdata[len(data) :] = 0
                raise sd.CallbackStop
            outdata[:] = data
        else:
            self._underrun_count += 1
            print(f"⚠ Underrun #{self._underrun_count}!", file=sys.stderr)
            outdata.fill(0)
            if self._sf is None:
                raise sd.CallbackStop

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def underrun_count(self) -> int:
        return self._underrun_count

    def play(self) -> None:
        """Запускает воспроизведение, блокирует до конца файла."""
        self._buffer = collections.deque()
        self._underrun_count = 0
        if self.filter is not None:
            self.filter.reset()

        self._sf = sf.SoundFile(self.audio_file)
        samplerate = self._sf.samplerate
        channels = self._sf.channels

        self._fill_buffer()

        with sd.OutputStream(
            samplerate=samplerate,
            channels=channels,
            blocksize=self.block_size,
            dtype="float32",
            callback=self._callback,
        ) as stream:
            label = type(self.filter).__name__ if self.filter else "без фильтра"
            print(f"▶ Однопоточный [{label}] | BUFFER_SIZE={self.buffer_size}")
            while stream.active:
                sd.sleep(10)

        if self._sf:
            self._sf.close()
            self._sf = None

        print(f"✅ Готово. Underrun: {self._underrun_count}")


# ----------------------------------------------------------------------
# Точка входа
# ----------------------------------------------------------------------

if __name__ == "__main__":
    iir = EllipticIIRFilter(order=4, rp=1.0, rs=70.0,
                             cutoff=4_000, btype="lowpass", fs=48_000)
    fir = TriangularFIRFilter(numtaps=500, cutoff=4_000, btype="highpass", fs=48_000)

    SingleThreadAudioBuffer("../input.wav", buffer_size=64,
                            block_size=1024, filter=fir).play()