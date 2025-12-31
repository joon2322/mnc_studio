"""파일 복사기"""

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from .config import WAV_EXTENSION, DIR_PERMISSION, FILE_PERMISSION
from .scanner import CopySession

logger = logging.getLogger(__name__)


@dataclass
class CopyResult:
    """복사 결과"""
    success: bool
    session: CopySession
    output_path: Optional[Path] = None
    files_copied: int = 0
    errors: List[str] = field(default_factory=list)


def copy_session(
    session: CopySession,
    output_base: Path,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> CopyResult:
    """
    세션의 WAV 파일 복사

    출력 구조: output_base/위치/지점/YYYYMMDD(요일)/

    Args:
        session: 복사 대상 세션
        output_base: 출력 루트 경로
        progress_callback: 진행 콜백 (current, total, message)

    Returns:
        CopyResult
    """
    result = CopyResult(success=True, session=session)

    # 출력 경로 생성
    output_path = output_base / session.location / session.point / session.date_folder_name

    try:
        output_path.mkdir(parents=True, exist_ok=True)
        output_path.chmod(DIR_PERMISSION)
    except Exception as e:
        result.success = False
        result.errors.append(f"폴더 생성 실패: {e}")
        return result

    result.output_path = output_path

    # WAV 파일 복사
    wav_files = sorted(session.source_path.glob(WAV_EXTENSION))
    total = len(wav_files)

    for idx, wav_file in enumerate(wav_files, 1):
        try:
            if progress_callback:
                progress_callback(idx, total, wav_file.name)

            dest_path = output_path / wav_file.name

            # 이미 존재하면 스킵
            if dest_path.exists():
                result.files_copied += 1
                continue

            shutil.copy2(wav_file, dest_path)
            dest_path.chmod(FILE_PERMISSION)
            result.files_copied += 1

        except Exception as e:
            error_msg = f"{wav_file.name}: {e}"
            result.errors.append(error_msg)
            logger.error(f"복사 실패: {error_msg}")

    if result.errors:
        result.success = False

    return result
