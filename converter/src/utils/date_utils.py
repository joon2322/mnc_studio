"""날짜 유틸리티"""

import re
from datetime import date, datetime
from typing import Optional

from ..config import WEEKDAY_KR


def get_korean_weekday(d: date) -> str:
    """
    날짜의 한글 요일 반환

    Args:
        d: 날짜

    Returns:
        한글 요일 (월, 화, 수, 목, 금, 토, 일)
    """
    return WEEKDAY_KR[d.weekday()]


def parse_date_from_folder(folder_name: str) -> Optional[date]:
    """
    폴더명에서 날짜 추출

    지원 형식:
    - YYYYMMDD_HHMMSS_HHMMSS (Fusion 세션)
    - YYYYMMDD (일반)
    - YYYY-MM-DD (ISO)

    Args:
        folder_name: 폴더명

    Returns:
        파싱된 날짜 또는 None
    """
    # Fusion 세션 형식: 20251204_115306_000000
    match = re.match(r'^(\d{8})_\d{6}_\d{6}$', folder_name)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d").date()
        except ValueError:
            pass

    # 일반 형식: 20251204
    match = re.match(r'^(\d{8})$', folder_name)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d").date()
        except ValueError:
            pass

    # ISO 형식: 2025-12-04
    match = re.match(r'^(\d{4}-\d{2}-\d{2})$', folder_name)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d").date()
        except ValueError:
            pass

    return None
