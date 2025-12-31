"""Fusion Audio BID → WAV 변환 프로세서"""

import logging
import re
import wave
from datetime import date
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from ..config import (
    FUSION_SAMPLE_RATE,
    FUSION_BID_BYTES_PER_SAMPLE,
    OUTPUT_CHANNELS,
    OUTPUT_SAMPLE_WIDTH,
    AUDIO_BID_PATTERN,
)
from ..utils.permissions import ensure_permissions
from .base_processor import BaseProcessor, ProcessingResult

logger = logging.getLogger(__name__)


class FusionProcessor(BaseProcessor):
    """Fusion Audio BID → WAV 변환 프로세서"""

    def __init__(self, measurement_date: Optional[date] = None):
        """
        Args:
            measurement_date: 측정일 (파일명 prefix용)
        """
        super().__init__()
        self.measurement_date = measurement_date

    def process(
        self,
        input_path: Path,
        output_path: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> ProcessingResult:
        """
        Audio 폴더의 모든 BID 파일을 WAV로 변환

        Args:
            input_path: Audio 폴더 경로 (BID 파일들이 있는 폴더)
            output_path: WAV 출력 폴더
            progress_callback: 진행 콜백 (current, total, message)

        Returns:
            ProcessingResult
        """
        result = ProcessingResult(
            success=True,
            input_path=input_path,
            output_path=output_path
        )

        # BID 파일 목록
        bid_files = sorted(input_path.glob(AUDIO_BID_PATTERN))

        if not bid_files:
            result.success = False
            result.message = "BID 파일 없음"
            return result

        total = len(bid_files)

        for idx, bid_file in enumerate(bid_files, 1):
            try:
                if progress_callback:
                    progress_callback(idx, total, f"변환 중: {bid_file.name}")

                output_filename = self.get_output_filename(bid_file)
                wav_path = output_path / output_filename

                self._convert_bid_to_wav(bid_file, wav_path)

                result.files_processed += 1

            except Exception as e:
                error_msg = f"{bid_file.name}: {e}"
                result.errors.append(error_msg)
                result.files_failed += 1
                self.logger.error(f"변환 실패: {error_msg}")

        if result.files_failed > 0:
            result.success = False
            result.message = f"{result.files_failed}개 파일 변환 실패"
        else:
            result.message = f"{result.files_processed}개 파일 변환 완료"

        return result

    def get_output_filename(self, input_file: Path) -> str:
        """
        출력 WAV 파일명 생성

        형식: YYYYMMDD_HHMMSS_HHMMSS.wav
        예: 20251205_200000_203000.wav

        Args:
            input_file: 입력 BID 파일 (예: 200000_203000.bid)

        Returns:
            출력 파일명
        """
        # BID 파일명에서 시간 추출
        match = re.match(r'^(\d{6})_(\d{6})\.bid$', input_file.name, re.IGNORECASE)

        if match and self.measurement_date:
            start_time = match.group(1)
            end_time = match.group(2)
            date_str = self.measurement_date.strftime("%Y%m%d")
            return f"{date_str}_{start_time}_{end_time}.wav"
        else:
            # 날짜 없으면 원본 이름 사용
            return input_file.stem + ".wav"

    def _convert_bid_to_wav(self, bid_path: Path, wav_path: Path) -> None:
        """
        BID 파일을 WAV로 변환

        핵심: 32-bit signed int → 16-bit signed int
        방법: >> 8 (오른쪽 시프트) - 품질 손실 없음

        Args:
            bid_path: 입력 BID 파일 경로
            wav_path: 출력 WAV 파일 경로
        """
        # BID 파일 읽기 (32-bit little-endian signed integer)
        raw_data = np.fromfile(bid_path, dtype='<i4')

        # 32-bit → 16-bit 변환 (오른쪽 시프트 8비트)
        # 이 방법은 클리핑 없이 전체 동적 범위를 보존함
        audio_16bit = (raw_data >> 8).astype(np.int16)

        # WAV 파일 쓰기
        with wave.open(str(wav_path), 'wb') as wav_file:
            wav_file.setnchannels(OUTPUT_CHANNELS)
            wav_file.setsampwidth(OUTPUT_SAMPLE_WIDTH)
            wav_file.setframerate(FUSION_SAMPLE_RATE)
            wav_file.writeframes(audio_16bit.tobytes())

        ensure_permissions(wav_path, is_directory=False)

        self.logger.debug(f"변환 완료: {bid_path.name} → {wav_path.name}")
