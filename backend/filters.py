import numpy as np
from scipy.signal import ellip, firwin, lfilter, lfilter_zi


class EllipticIIRFilter:

    def __init__(
        self,
        order: int = 4,
        rp: float = 1.0,
        rs: float = 70.0,
        cutoff: float | list[float] = 4_000.0,
        btype: str = "lowpass",
        fs: float | None = None,
    ):
        self.order = order
        self.rp = rp
        self.rs = rs
        self.cutoff = cutoff
        self.btype = btype
        self.fs = fs

        self._b, self._a = ellip(
            order, rp, rs, cutoff, btype=btype, analog=False, output="ba", fs=fs
        )
        self._zi: np.ndarray | None = None

    def reset(self) -> None:
        """Сбрасывает внутреннее состояние фильтра."""
        self._zi = None

    def process(self, x: np.ndarray, stateful: bool = True) -> np.ndarray:
        if not stateful:
            return lfilter(self._b, self._a, x, axis=0)

        if self._zi is None:
            zi_proto = lfilter_zi(self._b, self._a)           # (order,)
            if x.ndim == 2:
                self._zi = np.outer(zi_proto, np.ones(x.shape[1]))  # (order, ch)
            else:
                self._zi = zi_proto.copy()

        y, self._zi = lfilter(self._b, self._a, x, axis=0, zi=self._zi)
        return y


# ======================================================================


class TriangularFIRFilter:
    _PASS_ZERO = {
        "lowpass":  True,
        "highpass": False,
        "bandpass": False,
    }

    def __init__(
        self,
        numtaps: int = 101,
        cutoff: float | list[float] = 4_000.0,
        btype: str = "lowpass",
        fs: float | None = None,
    ):
        if btype not in self._PASS_ZERO:
            raise ValueError(f"btype должен быть одним из {list(self._PASS_ZERO)}, получено: {btype!r}")
        if numtaps % 2 == 0:
            numtaps += 1

        self.numtaps = numtaps
        self.cutoff = cutoff
        self.btype = btype
        self.fs = fs

        self._h = firwin(
            numtaps,
            cutoff,
            window="bartlett",
            pass_zero=self._PASS_ZERO[btype],
            fs=fs,
        )
        self._overlap: np.ndarray | None = None

    @property
    def group_delay(self) -> int:
        """Групповая задержка (сэмплов)."""
        return (self.numtaps - 1) // 2

    @property
    def coefficients(self) -> np.ndarray:
        """Коэффициенты импульсной характеристики h[n]."""
        return self._h.copy()

    def reset(self) -> None:
        """Сбрасывает буфер перекрытия."""
        self._overlap = None

    def process(self, x: np.ndarray, stateful: bool = True) -> np.ndarray:
        if not stateful:
            return lfilter(self._h, [1.0], x, axis=0)

        if self._overlap is None:
            channels = x.shape[1] if x.ndim == 2 else 1
            self._overlap = np.zeros(
                (self.numtaps - 1, channels), dtype=np.float32
            )

        x_2d = x if x.ndim == 2 else x[:, np.newaxis]
        x_ext = np.concatenate([self._overlap, x_2d], axis=0)
        y_ext = lfilter(self._h, [1.0], x_ext, axis=0)
        self._overlap = x_ext[-(self.numtaps - 1):]

        out = y_ext[self.numtaps - 1:]
        return out if x.ndim == 2 else out[:, 0]
