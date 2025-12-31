"""날짜/시간 유틸리티"""

import re
from datetime import date, datetime
from typing import Optional, Tuple


def parse_fusion_date(folder_name: str) -> Optional[date]:
    """
    Fusion 세션 폴더명에서 날짜 추출

    형식: YYYYMMDD_HHMMSS_HHMMSS
    예: 20251204_115306_000000 → 2025-12-04
    """
    match = re.match(r'^(\d{8})_\d{6}_\d{6}$', folder_name)
    if match:
        date_str = match.group(1)
        try:
            return datetime.strptime(date_str, "%Y%m%d").date()
        except ValueError:
            return None
    return None


def parse_fusion_session_duration(folder_name: str) -> Optional[int]:
    """
    Fusion 세션 폴더명에서 세션 길이(초) 계산

    형식: YYYYMMDD_HHMMSS_HHMMSS
    예: 20251204_115306_235306 → 12시간 = 43200초
    """
    match = re.match(r'^\d{8}_(\d{6})_(\d{6})$', folder_name)
    if match:
        start_str = match.group(1)
        end_str = match.group(2)
        try:
            start_time = datetime.strptime(start_str, "%H%M%S")
            end_time = datetime.strptime(end_str, "%H%M%S")

            # 자정을 넘어가는 경우 처리
            if end_time < start_time:
                # 다음날로 계산
                delta = (24 * 3600) - (start_time.hour * 3600 + start_time.minute * 60 + start_time.second)
                delta += end_time.hour * 3600 + end_time.minute * 60 + end_time.second
                return delta
            else:
                delta = end_time - start_time
                return int(delta.total_seconds())
        except ValueError:
            return None
    return None


def calculate_expected_bid_count(duration_sec: int, segment_duration: int = 1800) -> int:
    """
    예상 BID 파일 수 계산

    Args:
        duration_sec: 세션 길이 (초)
        segment_duration: 세그먼트 길이 (초), 기본 30분

    Returns:
        예상 파일 수
    """
    if duration_sec <= 0:
        return 0
    # 올림 처리
    return (duration_sec + segment_duration - 1) // segment_duration


def parse_audio_bid_time(filename: str) -> Tuple[int, int]:
    """
    Audio BID 파일명에서 시작/종료 시간(초) 추출

    형식: HHMMSS_HHMMSS.bid
    예: 115307_122307.bid → (42787, 45787)

    Returns:
        (start_seconds, end_seconds)

    Raises:
        ValueError: 파일명 형식 오류
    """
    match = re.match(r'^(\d{6})_(\d{6})\.bid$', filename, re.IGNORECASE)
    if not match:
        raise ValueError(f"잘못된 파일명 형식: {filename}")

    start_str = match.group(1)
    end_str = match.group(2)

    try:
        start_h, start_m, start_s = int(start_str[:2]), int(start_str[2:4]), int(start_str[4:6])
        end_h, end_m, end_s = int(end_str[:2]), int(end_str[2:4]), int(end_str[4:6])

        start_sec = start_h * 3600 + start_m * 60 + start_s
        end_sec = end_h * 3600 + end_m * 60 + end_s

        # 자정을 넘어가는 경우
        if end_sec < start_sec:
            end_sec += 24 * 3600

        return start_sec, end_sec
    except (ValueError, IndexError) as e:
        raise ValueError(f"시간 파싱 실패: {filename} - {e}")
