"""Fusion Audio BID 파일 검증"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from ..config import (
    FUSION_SAMPLE_RATE,
    FUSION_BID_BYTES_PER_SAMPLE,
    FUSION_SEGMENT_DURATION,
    AUDIO_BID_PATTERN,
)

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """검증 결과"""
    is_valid: bool
    message: str
    expected_samples: Optional[int] = None
    actual_samples: Optional[int] = None
    file_size: Optional[int] = None


def validate_fusion_audio_bid(file_path: Path) -> ValidationResult:
    """
    단일 Audio BID 파일 검증

    검증 항목:
    - 파일 존재 여부
    - 파일 크기 (30분 = 46,080,000 bytes)
    - 샘플 수 일치

    Args:
        file_path: BID 파일 경로

    Returns:
        ValidationResult
    """
    if not file_path.exists():
        return ValidationResult(
            is_valid=False,
            message=f"파일 없음: {file_path.name}"
        )

    file_size = file_path.stat().st_size

    # 예상 크기: 30분 * 60초 * 25600 samples/sec * 4 bytes/sample
    expected_samples = FUSION_SEGMENT_DURATION * FUSION_SAMPLE_RATE
    expected_size = expected_samples * FUSION_BID_BYTES_PER_SAMPLE

    actual_samples = file_size // FUSION_BID_BYTES_PER_SAMPLE

    if file_size != expected_size:
        return ValidationResult(
            is_valid=False,
            message=f"크기 불일치: {file_size:,} bytes (예상: {expected_size:,})",
            expected_samples=expected_samples,
            actual_samples=actual_samples,
            file_size=file_size
        )

    return ValidationResult(
        is_valid=True,
        message="정상",
        expected_samples=expected_samples,
        actual_samples=actual_samples,
        file_size=file_size
    )


def validate_fusion_audio_folder(folder_path: Path) -> List[ValidationResult]:
    """
    Audio 폴더 내 모든 BID 파일 검증

    Args:
        folder_path: Audio 폴더 경로

    Returns:
        각 파일의 ValidationResult 리스트
    """
    results = []

    if not folder_path.exists():
        return [ValidationResult(
            is_valid=False,
            message=f"폴더 없음: {folder_path}"
        )]

    bid_files = sorted(folder_path.glob(AUDIO_BID_PATTERN))

    if not bid_files:
        return [ValidationResult(
            is_valid=False,
            message=f"BID 파일 없음: {folder_path}"
        )]

    for bid_file in bid_files:
        result = validate_fusion_audio_bid(bid_file)
        results.append(result)

    return results
