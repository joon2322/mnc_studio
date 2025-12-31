"""권한 유틸리티"""

import logging
import os
from pathlib import Path

from ..config import DIR_PERMISSION, FILE_PERMISSION

logger = logging.getLogger(__name__)


def ensure_permissions(path: Path, is_directory: bool = False) -> None:
    """
    파일/폴더 권한 설정

    Args:
        path: 대상 경로
        is_directory: 디렉토리 여부
    """
    try:
        permission = DIR_PERMISSION if is_directory else FILE_PERMISSION
        os.chmod(path, permission)
    except Exception as e:
        logger.warning(f"권한 설정 실패 (무시): {path} - {e}")
