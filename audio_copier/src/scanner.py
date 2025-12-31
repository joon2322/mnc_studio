"""세션 스캐너"""

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

from .config import WAV_EXTENSION, WEEKDAY_KR

logger = logging.getLogger(__name__)


@dataclass
class CopySession:
    """복사 대상 세션"""
    location: str
    point: str
    measurement_date: date
    weekday: str
    source_path: Path
    wav_count: int

    @property
    def date_folder_name(self) -> str:
        """날짜 폴더명 (예: 20251205(금))"""
        return f"{self.measurement_date.strftime('%Y%m%d')}({self.weekday})"


def parse_date_folder(folder_name: str) -> Optional[date]:
    """
    날짜 폴더명에서 날짜 추출

    형식: YYYYMMDD(요일) 또는 YYYYMMDD
    예: 20251205(금) → 2025-12-05
    """
    match = re.match(r'^(\d{8})(?:\([가-힣]\))?$', folder_name)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d").date()
        except ValueError:
            return None
    return None


def scan_sessions(source_path: Path) -> List[CopySession]:
    """
    소스 경로에서 세션 스캔

    구조: source_path/위치/지점/YYYYMMDD(요일)/

    Args:
        source_path: 소스 루트 경로

    Returns:
        CopySession 리스트
    """
    sessions = []

    if not source_path.exists():
        logger.warning(f"소스 경로 없음: {source_path}")
        return sessions

    # 위치 폴더 탐색
    for location_dir in source_path.iterdir():
        if not location_dir.is_dir():
            continue

        location = location_dir.name

        # 지점 폴더 탐색
        for point_dir in location_dir.iterdir():
            if not point_dir.is_dir():
                continue

            point = point_dir.name

            # 날짜 폴더 탐색
            for date_dir in point_dir.iterdir():
                if not date_dir.is_dir():
                    continue

                measurement_date = parse_date_folder(date_dir.name)
                if measurement_date is None:
                    continue

                # WAV 파일 수 확인
                wav_files = list(date_dir.glob(WAV_EXTENSION))
                if not wav_files:
                    continue

                weekday_idx = measurement_date.weekday()
                weekday = WEEKDAY_KR[weekday_idx]

                session = CopySession(
                    location=location,
                    point=point,
                    measurement_date=measurement_date,
                    weekday=weekday,
                    source_path=date_dir,
                    wav_count=len(wav_files)
                )
                sessions.append(session)

    # 정렬: 위치 → 지점 → 날짜
    sessions.sort(key=lambda s: (s.location, s.point, s.measurement_date))

    logger.info(f"스캔 완료: {len(sessions)}개 세션")
    return sessions
