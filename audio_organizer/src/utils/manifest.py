"""Manifest 생성 유틸리티"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import MANIFEST_VERSION, MANIFEST_FILENAME
from .permissions import ensure_permissions

logger = logging.getLogger(__name__)


def create_manifest(
    session_path: Path,
    source_path: Path,
    equipment_type: str,
    measurement_date: str,
    extra_info: Optional[dict] = None,
) -> Path:
    """
    세션 manifest.json 생성

    Args:
        session_path: 세션 출력 폴더
        source_path: 원본 경로
        equipment_type: 장비 유형
        measurement_date: 측정일
        extra_info: 추가 정보

    Returns:
        생성된 manifest 파일 경로
    """
    manifest_path = session_path / MANIFEST_FILENAME

    # WAV 파일 목록
    wav_files = sorted([f.name for f in session_path.glob("*.wav")])

    manifest_data = {
        "version": MANIFEST_VERSION,
        "created_at": datetime.now().isoformat(),
        "source_path": str(source_path),
        "equipment_type": equipment_type,
        "measurement_date": measurement_date,
        "file_count": len(wav_files),
        "files": wav_files,
    }

    if extra_info:
        manifest_data.update(extra_info)

    try:
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest_data, f, ensure_ascii=False, indent=2)
        ensure_permissions(manifest_path, is_directory=False)
        logger.info(f"Manifest 생성: {manifest_path}")
        return manifest_path
    except Exception as e:
        logger.error(f"Manifest 생성 실패: {manifest_path} - {e}")
        raise
