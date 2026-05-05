import soundfile as sf
import numpy as np
from typing import Callable

from backend.single_thread_audio_buffer import SingleThreadAudioBuffer
from backend.dual_thread_audio_buffer import DualThreadAudioBuffer
from backend.equalizer import Equalizer
from backend.effects import EffectsChain


class AudioPlayer:

    def __init__(
            self,
            audio_file: str,
            buffer_size: int = 8192,
            block_size: int = 1024,
            use_dual_thread: bool = True,
            equalizer: Equalizer | None = None,
            start_frame: int = 0,
            effects_chain: EffectsChain | None = None,
    ):
        self.audio_file = audio_file
        self.equalizer = equalizer
        self.effects_chain = effects_chain
        self.start_frame = start_frame
        self._frames_played = 0
        self.on_block = None

        # Создаём нужный буфер — filter=None, обработку делаем сами
        if use_dual_thread:
            self._buffer = DualThreadAudioBuffer(
                audio_file=audio_file,
                buffer_size=buffer_size,
                block_size=block_size,
                filter=None,
            )
        else:
            self._buffer = SingleThreadAudioBuffer(
                audio_file=audio_file,
                buffer_size=buffer_size,
                block_size=block_size,
                filter=None,
            )

    # ------------------------------------------------------------------
    # Управление на лету (вызывается из GUI)
    # ------------------------------------------------------------------

    def set_gain(self, band: int, gain_db: float) -> None:
        if self.equalizer:
            self.equalizer.set_gain(band, gain_db)

    def set_filter_type(self, use_fir: bool) -> None:
        if self.equalizer:
            self.equalizer.set_filter_type(use_fir)

    def set_chorus(self, enabled: bool) -> None:
        if self.effects_chain:
            self.effects_chain.chorus_enabled = enabled

    def set_vibrato(self, enabled: bool) -> None:
        if self.effects_chain:
            self.effects_chain.vibrato_enabled = enabled

    def set_chorus_depth(self, depth_ms: float) -> None:
        if self.effects_chain:
            self.effects_chain.chorus.depth_ms = depth_ms

    def set_chorus_rate(self, rate_hz: float) -> None:
        if self.effects_chain:
            self.effects_chain.chorus.rate_hz = rate_hz

    def set_chorus_mix(self, mix: float) -> None:
        if self.effects_chain:
            self.effects_chain.chorus.mix = mix

    def set_chorus_voices(self, voices: int) -> None:
        if self.effects_chain:
            c = self.effects_chain.chorus
            c.voices = voices
            c._lfo_phases = np.linspace(0, 2 * np.pi, voices, endpoint=False)

    def set_vibrato_depth(self, depth_ms: float) -> None:
        if self.effects_chain:
            self.effects_chain.vibrato.depth_ms = depth_ms

    def set_vibrato_rate(self, rate_hz: float) -> None:
        if self.effects_chain:
            self.effects_chain.vibrato.rate_hz = rate_hz

    def set_iir_order_lp(self, order: int) -> None:
        if self.equalizer:
            self.equalizer.set_iir_order_lp(order)

    def set_iir_order_hp(self, order: int) -> None:
        if self.equalizer:
            self.equalizer.set_iir_order_hp(order)

    def set_iir_order_bp(self, order: int) -> None:
        if self.equalizer:
            self.equalizer.set_iir_order_bp(order)

    def set_fir_taps_lp(self, taps: int) -> None:
        if self.equalizer:
            self.equalizer.set_fir_taps_lp(taps)

    def set_fir_taps_hp(self, taps: int) -> None:
        if self.equalizer:
            self.equalizer.set_fir_taps_hp(taps)

    def set_fir_taps_bp(self, taps: int) -> None:
        if self.equalizer:
            self.equalizer.set_fir_taps_bp(taps)

    # ------------------------------------------------------------------
    # play()
    # ------------------------------------------------------------------

    def play(self) -> None:
        """
        Читает файл в буфер → эквалайзер → эффекты → звуковая карта.

        Проблема: буферы обрабатывают блоки внутри своего _callback,
        а нам нужно вклиниться между get() и outdata.
        Решение: подменяем filter на обёртку-пайплайн.
        """
        self._buffer.start_frame = self.start_frame
        self._buffer._frames_played = 0
        pipeline = _ProcessingPipeline(self.equalizer, self.effects_chain, self)
        self._buffer.filter = pipeline

        if self.equalizer:
            with sf.SoundFile(self.audio_file) as f:
                if self.equalizer.fs != f.samplerate:
                    print(f"⚠ fs эквалайзера ({self.equalizer.fs}) != fs файла ({f.samplerate})")

        self._buffer.play()

    @property
    def current_frame(self) -> int:
        return self.start_frame + self._buffer.frames_played

    def stop(self) -> None:
        # DualThreadAudioBuffer останавливается через stop_event
        if hasattr(self._buffer, '_stop_event'):
            self._buffer._stop_event.set()


class _ProcessingPipeline:
    """
    Обёртка, которая притворяется фильтром для буфера,
    но внутри прогоняет блок через эквалайзер и эффекты.

    Буфер вызывает: filter.process(block, stateful=True)
    Мы просто реализуем этот метод.
    """

    def __init__(self, equalizer: Equalizer | None, effects_chain: EffectsChain | None, player):
        self.equalizer = equalizer
        self.effects_chain = effects_chain
        self._player = player

    def reset(self) -> None:
        if self.equalizer:
            self.equalizer.reset()
        if self.effects_chain:
            self.effects_chain.reset()

    def process(self, block, stateful: bool = True):
        try:
            if self.equalizer:
                block = self.equalizer.process(block)
            if self.effects_chain:
                block = self.effects_chain.process(block)
            cb = self._player.on_block
            if cb is not None:
                cb(block)
            return block
        except Exception as e:
            import sys
            print(f"⚠ Pipeline error: {e}", file=sys.stderr)
            return block


# ----------------------------------------------------------------------
# Точка входа
# ----------------------------------------------------------------------

if __name__ == "__main__":
    eq = Equalizer(use_fir=False , fs=44100)
    eq.set_gains([0, 0, 0, 0, 0, 0, 0, -40])

    fx = EffectsChain(fs=44100)
    fx.chorus_enabled = False
    fx.vibrato_enabled = False


    player = AudioPlayer(
        audio_file="../input.wav",
        buffer_size=1,
        block_size=8192,
        use_dual_thread=True,
        equalizer=eq,
        effects_chain=fx,
    )
    player.play()