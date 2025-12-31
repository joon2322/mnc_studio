"""날짜/요일 처리 유틸리티"""

from datetime import datetime

# 한글 요일 (월요일 = 0)
WEEKDAY_KR = ['월', '화', '수', '목', '금', '토', '일']


def get_weekday_kr(date: datetime) -> str:
    """
    한글 요일 반환

    Args:
        date: datetime 객체

    Returns:
        한글 요일 (월, 화, 수, 목, 금, 토, 일)
    """
    return WEEKDAY_KR[date.weekday()]


def format_date_with_weekday(date: datetime) -> str:
    """
    날짜_요일 형식 반환

    Args:
        date: datetime 객체

    Returns:
        예: 20251127_목
    """
    return f"{date.strftime('%Y%m%d')}_{get_weekday_kr(date)}"
