"""사사오입 반올림 유틸리티

Python 기본 round()는 Banker's Rounding (짝수로 반올림)을 사용하므로
외부 변환기와 100% 호환을 위해 ROUND_HALF_UP 방식 사용

예: round_half_up(34.25, 1) = 34.3  (Python round는 34.2)
"""

from decimal import Decimal, ROUND_HALF_UP
import numpy as np
import pandas as pd
from typing import Union


def round_half_up(value: float, decimals: int = 1) -> float:
    """
    단일 값 사사오입 반올림 (0.5는 항상 올림)

    Args:
        value: 반올림할 값
        decimals: 소수점 자릿수 (기본 1)

    Returns:
        반올림된 값
    """
    if pd.isna(value):
        return value
    d = Decimal(str(value))
    return float(d.quantize(Decimal(10) ** -decimals, rounding=ROUND_HALF_UP))


def round_array_half_up(arr: np.ndarray, decimals: int = 1) -> np.ndarray:
    """
    배열 사사오입 반올림 (벡터화 최적화)

    Args:
        arr: numpy 배열
        decimals: 소수점 자릿수 (기본 1)

    Returns:
        반올림된 배열
    """
    multiplier = 10 ** decimals
    return np.floor(arr * multiplier + 0.5) / multiplier
