import numpy as np
from backend.filters import EllipticIIRFilter, TriangularFIRFilter

# 8 полос эквалайзера (Гц): граничные частоты [low, high]
# Стандартное октавное разбиение 20–20000 Гц
BANDS = [
    (20, 100),  # Band 1
    (100, 256),  # Band 2
    (256, 568),  # Band 3
    (568, 1192),  # Band 4
    (1192, 2440),  # Band 5
    (2440, 4936),  # Band 6
    (4936, 9928),  # Band 7
    (9928, 20000),  # Band 8
]

SAMPLE_RATE = 44100

# Параметры фильтров согласно ТЗ
IIR_ORDER_LP = 6
FIR_TAPS_LP = 1001  # нечётное >= 1000
IIR_ORDER_HP = 6
FIR_TAPS_HP = 501  # нечётное >= 500
IIR_ORDER_BP = 4
FIR_TAPS_BP = 751  # нечётное >= 750

RS = 70.0  # ослабление в полосе подавления, дБ
RP = 1.0  # пульсация в полосе пропускания, дБ


def _make_filter(low: float, high: float, use_fir: bool, fs: int):
    """
    Создаёт нужный тип фильтра для полосы [low, high].
    Крайние полосы — ФНЧ/ФВЧ, остальные — полосовой.
    """
    nyq = fs / 2.0

    # Первая полоса — ФНЧ с верхней границей
    if low <= 20:
        cutoff = min(high, nyq - 1)
        if use_fir:
            return TriangularFIRFilter(FIR_TAPS_LP, cutoff, btype="lowpass", fs=fs)
        else:
            return EllipticIIRFilter(IIR_ORDER_LP, RP, RS, cutoff, btype="lowpass", fs=fs)

    # Последняя полоса — ФВЧ с нижней границей
    if high >= 20000:
        cutoff = max(low, 1.0)
        if use_fir:
            return TriangularFIRFilter(FIR_TAPS_HP, cutoff, btype="highpass", fs=fs)
        else:
            return EllipticIIRFilter(IIR_ORDER_HP, RP, RS, cutoff, btype="highpass", fs=fs)

    # Остальные — полосовые
    cutoff = [max(low, 1.0), min(high, nyq - 1)]
    if use_fir:
        return TriangularFIRFilter(FIR_TAPS_BP, cutoff, btype="bandpass", fs=fs)
    else:
        return EllipticIIRFilter(IIR_ORDER_BP, RP, RS, cutoff, btype="bandpass", fs=fs)


class Equalizer:
    """
    8-полосный эквалайзер.

    use_fir: True  → КИХ (треугольное окно Бартлетта)
             False → БИХ (эллиптический фильтр)
    gains_db: список из 8 значений усиления в дБ (0.0 по умолчанию)
    """

    def __init__(self, use_fir: bool = True, fs: int = SAMPLE_RATE):
        self.fs = fs
        self.use_fir = use_fir
        self._gains_db: list[float] = [0.0] * 8
        self._filters = self._build_filters()

    def _build_filters(self) -> list:
        return [
            _make_filter(low, high, self.use_fir, self.fs)
            for low, high in BANDS
        ]

    def set_filter_type(self, use_fir: bool) -> None:
        """Переключает между КИХ и БИХ, перестраивает фильтры."""
        if self.use_fir == use_fir:
            return
        self.use_fir = use_fir
        self._filters = self._build_filters()

    def set_gain(self, band: int, gain_db: float) -> None:
        """Устанавливает усиление для полосы band (0–7) в дБ."""
        if not 0 <= band < 8:
            raise ValueError(f"Полоса должна быть 0–7, получено: {band}")
        self._gains_db[band] = gain_db

    def set_gains(self, gains_db: list[float]) -> None:
        """Устанавливает все 8 усилений разом."""
        if len(gains_db) != 8:
            raise ValueError("Нужно ровно 8 значений усиления")
        self._gains_db = list(gains_db)

    def set_iir_order_lp(self, order: int) -> None:
        global IIR_ORDER_LP
        IIR_ORDER_LP = order
        self._filters = self._build_filters()

    def set_iir_order_hp(self, order: int) -> None:
        global IIR_ORDER_HP
        IIR_ORDER_HP = order
        self._filters = self._build_filters()

    def set_iir_order_bp(self, order: int) -> None:
        global IIR_ORDER_BP
        IIR_ORDER_BP = order
        self._filters = self._build_filters()

    def set_fir_taps_lp(self, taps: int) -> None:
        global FIR_TAPS_LP
        FIR_TAPS_LP = taps if taps % 2 != 0 else taps + 1
        self._filters = self._build_filters()

    def set_fir_taps_hp(self, taps: int) -> None:
        global FIR_TAPS_HP
        FIR_TAPS_HP = taps if taps % 2 != 0 else taps + 1
        self._filters = self._build_filters()

    def set_fir_taps_bp(self, taps: int) -> None:
        global FIR_TAPS_BP
        FIR_TAPS_BP = taps if taps % 2 != 0 else taps + 1
        self._filters = self._build_filters()

    def reset(self) -> None:
        """Сбрасывает состояние всех фильтров (при смене трека)."""
        for f in self._filters:
            f.reset()

    def process(self, block: np.ndarray) -> np.ndarray:
        """
        Обрабатывает один блок аудио.
        block: np.ndarray shape (N,) или (N, channels), dtype float32
        Возвращает: np.ndarray того же shape
        """
        out = np.zeros_like(block, dtype=np.float64)
        for i, (filt, gain_db) in enumerate(zip(self._filters, self._gains_db)):
            if gain_db == -96.0:  # полное отключение полосы
                continue
            linear_gain = 10 ** (gain_db / 20.0)
            band_signal = filt.process(block, stateful=True)
            out += linear_gain * band_signal

        out = np.clip(out, -1.0, 1.0)
        return out.astype(np.float32)