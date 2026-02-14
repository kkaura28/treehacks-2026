# analysis/src/signal_processing.py
from __future__ import annotations

import numpy as np


def ema(x: np.ndarray, alpha: float) -> np.ndarray:
    """Exponential moving average. alpha blends toward the new value."""
    if x.size == 0:
        return x
    y = np.empty_like(x, dtype=float)
    y[0] = float(x[0])
    for i in range(1, len(x)):
        y[i] = alpha * float(x[i]) + (1.0 - alpha) * float(y[i - 1])
    return y
