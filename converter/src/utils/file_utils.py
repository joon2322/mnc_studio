"""파일명 유틸리티"""

import re
from datetime import date
from typing import Optional

from .date_utils import get_korean_weekday


def normalize_point_name(folder_name: str) -> str:
    """
    폴더명에서 정규화된 지점명 추출

    변환 규칙:
    - "N01 지점명" → "N-1"
    - "N10 지점명" → "N-10"
    - "이동식 N01 지점명" → "이동식1"
    - "이동식 N07 지점명" → "이동식7"

    Args:
        folder_name: 원본 폴더명

    Returns:
        정규화된 지점명
    """
    name = folder_name.strip()

    # 이동식 패턴: "이동식 N01 ..." → "이동식1"
    match = re.match(r'^이동식\s*N?0*(\d+)', name, re.IGNORECASE)
    if match:
        num = int(match.group(1))
        return f"이동식{num}"

    # 일반 N 패턴: "N01 ..." → "N-1"
    match = re.match(r'^N-?0*(\d+)', name, re.IGNORECASE)
    if match:
        num = int(match.group(1))
        return f"N-{num}"

    # 매칭 안되면 원본 반환 (공백 제거)
    return name.split()[0] if ' ' in name else name


def generate_output_filename(
    location: str,
    order: Optional[str],
    point: str,
    measurement_date: date,
    weighting: str,
    extension: str = ".parquet"
) -> str:
    """
    출력 파일명 생성

    형식: {위치}_{차수}_{지점}_{측정일자}_{요일}_{가중치}.parquet
    차수가 없으면: {위치}_{지점}_{측정일자}_{요일}_{가중치}.parquet

    Args:
        location: 위치명 (예: 광주비행장)
        order: 차수 (예: 1차, 2차 또는 None)
        point: 지점 (예: N-1)
        measurement_date: 측정일
        weighting: 가중치 (LAS 또는 LCS)
        extension: 확장자 (기본 .parquet)

    Returns:
        파일명
    """
    date_str = measurement_date.strftime("%Y%m%d")
    weekday = get_korean_weekday(measurement_date)

    if order:
        return f"{location}_{order}_{point}_{date_str}_{weekday}_{weighting}{extension}"
    else:
        return f"{location}_{point}_{date_str}_{weekday}_{weighting}{extension}"
