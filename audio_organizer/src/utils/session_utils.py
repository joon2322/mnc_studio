"""세션 유틸리티"""

import logging
from datetime import date
from pathlib import Path
from typing import Optional

from ..config import WEEKDAY_KR, DIR_PERMISSION
from .permissions import ensure_permissions

logger = logging.getLogger(__name__)


def create_session_folder(
    base_path: Path,
    location: str,
    point: str,
    measurement_date: date,
) -> Optional[Path]:
    """
    세션 출력 폴더 생성

    구조: base_path/location/point/YYYYMMDD(요일)/
    또는: base_path/point/YYYYMMDD(요일)/ (location이 비어있는 경우)

    Returns:
        생성된 폴더 경로, 이미 존재하면 None
    """
    weekday_idx = measurement_date.weekday()
    weekday_kr = WEEKDAY_KR[weekday_idx]
    date_folder = f"{measurement_date.strftime('%Y%m%d')}({weekday_kr})"

    if location:
        session_path = base_path / location / point / date_folder
    else:
        session_path = base_path / point / date_folder

    if session_path.exists():
        logger.warning(f"세션 폴더 이미 존재: {session_path}")
        return None

    try:
        session_path.mkdir(parents=True, exist_ok=False)
        ensure_permissions(session_path, is_directory=True)
        logger.info(f"세션 폴더 생성: {session_path}")
        return session_path
    except FileExistsError:
        logger.warning(f"세션 폴더 이미 존재: {session_path}")
        return None
    except Exception as e:
        logger.error(f"세션 폴더 생성 실패: {session_path} - {e}")
        raise
