"""사사오입 반올림 유틸리티"""

from decimal import Decimal, ROUND_HALF_UP


def round_half_up(value: float, decimals: int = 1) -> float:
    """
    사사오입 반올림 (ROUND_HALF_UP)

    Python의 기본 round()는 은행원 반올림(Banker's rounding)을 사용하여
    .5에서 짝수로 반올림합니다. 이 함수는 일반적인 사사오입을 구현합니다.

    예:
        round_half_up(34.25, 1) → 34.3  (Python round는 34.2)
        round_half_up(34.35, 1) → 34.4

    Args:
        value: 반올림할 값
        decimals: 소수점 자릿수 (기본 1)

    Returns:
        사사오입 반올림된 값
    """
    d = Decimal(str(value))
    quantize_exp = Decimal(10) ** -decimals
    return float(d.quantize(quantize_exp, rounding=ROUND_HALF_UP))
