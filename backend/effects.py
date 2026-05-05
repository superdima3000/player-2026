import numpy as np

SAMPLE_RATE = 44100


class ChorusEffect:
    """
    Эффект хора: несколько задержанных копий сигнала с LFO-модуляцией.

    voices:     количество голосов (2–4)
    depth_ms:   глубина модуляции задержки, мс
    rate_hz:    частота LFO, Гц
    mix:        0.0 = сухой сигнал, 1.0 = только эффект
    """

    def __init__(
            self,
            voices: int = 3,
            depth_ms: float = 10.0,
            rate_hz: float = 1.5,
            mix: float = 0.5,
            fs: int = SAMPLE_RATE,
    ):
        self.voices = voices
        self.depth_ms = depth_ms
        self.rate_hz = rate_hz
        self.mix = mix
        self.fs = fs

        self._max_delay = int(fs * 0.05)  # 50 мс максимальная задержка
        self._buffer = np.zeros((self._max_delay + 1,), dtype=np.float64)
        self._buf_ptr = 0
        self._lfo_phases = np.linspace(0, 2 * np.pi, voices, endpoint=False)
        self._sample_count = 0

    def reset(self) -> None:
        self._buffer[:] = 0.0
        self._buf_ptr = 0
        self._sample_count = 0

    def process(self, block: np.ndarray) -> np.ndarray:
        """
        Принимает моно или стерео блок (N,) / (N, ch).
        Хор применяется по первому каналу / моно.
        """
        mono = block[:, 0] if block.ndim == 2 else block
        mono = np.nan_to_num(mono, nan=0.0, posinf=1.0, neginf=-1.0)
        out_mono = np.zeros(len(mono), dtype=np.float64)
        depth_samples = (self.depth_ms / 1000.0) * self.fs
        base_delay = int(self._max_delay * 0.4)  # базовая задержка ~20 мс

        for n, x in enumerate(mono.astype(np.float64)):
            self._buffer[self._buf_ptr] = x
            mix_sum = 0.0

            for v in range(self.voices):
                phase = self._lfo_phases[v] + 2 * np.pi * self.rate_hz * self._sample_count / self.fs
                delay = base_delay + depth_samples * np.sin(phase)
                delay_int = int(delay) % self._max_delay
                read_ptr = (self._buf_ptr - delay_int) % (self._max_delay + 1)
                mix_sum += self._buffer[read_ptr]

            out_mono[n] = (1.0 - self.mix) * x + self.mix * (mix_sum / self.voices)
            self._buf_ptr = (self._buf_ptr + 1) % (self._max_delay + 1)
            self._sample_count += 1

        # Обновляем LFO-фазы между блоками
        self._lfo_phases += 2 * np.pi * self.rate_hz * len(mono) / self.fs

        if block.ndim == 2:
            result = block.copy().astype(np.float32)
            result[:, 0] = out_mono.astype(np.float32)
            if block.shape[1] > 1:
                result[:, 1] = out_mono.astype(np.float32)
            return result
        return out_mono.astype(np.float32)


class VibratoEffect:
    """
    Эффект вибрато: модуляция высоты тона через переменную задержку.

    depth_ms:  глубина модуляции задержки, мс (рекомендуется 3–8)
    rate_hz:   частота модуляции, Гц (рекомендуется 4–7)
    """

    def __init__(
            self,
            depth_ms: float = 5.0,
            rate_hz: float = 5.0,
            fs: int = SAMPLE_RATE,
    ):
        self.depth_ms = depth_ms
        self.rate_hz = rate_hz
        self.fs = fs

        self._max_delay = int(fs * 0.02)  # 20 мс буфер
        self._buffer = np.zeros(self._max_delay + 1, dtype=np.float64)
        self._buf_ptr = 0
        self._sample_count = 0

    def reset(self) -> None:
        self._buffer[:] = 0.0
        self._buf_ptr = 0
        self._sample_count = 0

    def process(self, block: np.ndarray) -> np.ndarray:
        mono = block[:, 0] if block.ndim == 2 else block
        mono = np.nan_to_num(mono, nan=0.0, posinf=1.0, neginf=-1.0)
        out_mono = np.zeros(len(mono), dtype=np.float64)
        depth_samples = (self.depth_ms / 1000.0) * self.fs

        for n, x in enumerate(mono.astype(np.float64)):
            self._buffer[self._buf_ptr] = x
            phase = 2 * np.pi * self.rate_hz * self._sample_count / self.fs
            delay = depth_samples * (1.0 + np.sin(phase)) / 2.0

            # Линейная интерполяция для плавного звука
            delay_int = int(delay)
            frac = delay - delay_int
            ptr0 = (self._buf_ptr - delay_int) % (self._max_delay + 1)
            ptr1 = (self._buf_ptr - delay_int - 1) % (self._max_delay + 1)
            out_mono[n] = (1.0 - frac) * self._buffer[ptr0] + frac * self._buffer[ptr1]

            self._buf_ptr = (self._buf_ptr + 1) % (self._max_delay + 1)
            self._sample_count += 1

        if block.ndim == 2:
            result = block.copy().astype(np.float32)
            result[:, 0] = out_mono.astype(np.float32)
            if block.shape[1] > 1:
                result[:, 1] = out_mono.astype(np.float32)
            return result
        return out_mono.astype(np.float32)




class EffectsChain:
    """
    Цепочка эффектов. Включение/выключение через флаги.
    Порядок: Equalizer → Chorus → Vibrato
    (Эквалайзер подключается снаружи, здесь только пост-эффекты)
    """

    def __init__(self, fs: int = SAMPLE_RATE):
        self.chorus = ChorusEffect(fs=fs)
        self.vibrato = VibratoEffect(fs=fs)
        self.chorus_enabled = False
        self.vibrato_enabled = False

    def reset(self) -> None:
        self.chorus.reset()
        self.vibrato.reset()

    def process(self, block: np.ndarray) -> np.ndarray:
        if self.chorus_enabled:
            block = self.chorus.process(block)
        if self.vibrato_enabled:
            block = self.vibrato.process(block)
        return block

