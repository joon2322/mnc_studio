"""Fusion Audio BID → WAV 변환 프로세서

정식 Fusion 프로그램과 동일한 32-bit 피크 정규화 출력.
검증: 미여도, 낙동, 수원 데이터에서 100% 샘플 일치 확인.
"""

import logging
import re
import wave
from datetime import date
from pathlib import Path
from typing import Callable, Optional, Tuple

import numpy as np

from ..config import (
    FUSION_SAMPLE_RATE,  # 기본값으로만 사용
    FUSION_BID_BYTES_PER_SAMPLE,
    OUTPUT_CHANNELS,
    OUTPUT_SAMPLE_WIDTH,
    AUDIO_BID_PATTERN,
    FUSION_FULL_SCALE,  # 정식 프로그램 피크 정규화 상수
)
from ..utils.permissions import ensure_permissions
from .base_processor import BaseProcessor, ProcessingResult

logger = logging.getLogger(__name__)


class FusionProcessor(BaseProcessor):
    """Fusion Audio BID → WAV 변환 프로세서"""

    def __init__(
        self,
        measurement_date: Optional[date] = None,
        sample_rate: int = FUSION_SAMPLE_RATE,
    ):
        """
        Args:
            measurement_date: 측정일 (파일명 prefix용)
            sample_rate: 샘플레이트 (Hz), 세션별로 다를 수 있음
        """
        super().__init__()
        self.measurement_date = measurement_date
        self.sample_rate = sample_rate

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

    def _convert_bid_to_wav(self, bid_path: Path, wav_path: Path) -> Tuple[int, float]:
        """
        BID 파일을 WAV로 변환 (32-bit 피크 정규화)

        정식 Fusion 프로그램과 동일한 알고리즘:
        1. BID 원본 데이터의 절댓값 최대치(max_abs) 계산
        2. 스케일 팩터 = FULL_SCALE / max_abs
        3. 정수 나눗셈으로 스케일링 (부호 보존)

        검증: 미여도, 낙동, 수원 데이터에서 100% 샘플 일치 확인

        Args:
            bid_path: 입력 BID 파일 경로
            wav_path: 출력 WAV 파일 경로

        Returns:
            Tuple[int, float]: (max_abs, scale_factor)
        """
        # BID 파일 읽기 (32-bit little-endian signed integer)
        raw_data = np.fromfile(bid_path, dtype='<i4')

        # 64-bit로 변환하여 오버플로우 방지
        raw_64 = raw_data.astype(np.int64)

        # 피크값 계산
        max_abs = int(np.max(np.abs(raw_64)))

        if max_abs == 0:
            # 무음 파일 처리
            scaled_data = raw_data
            scale_factor = 0.0
        else:
            # 정식 프로그램 알고리즘: 정수 나눗셈 (truncation)
            # num = raw * FULL_SCALE
            # scaled = sign(num) * (abs(num) // max_abs)
            num = raw_64 * FUSION_FULL_SCALE
            scaled_data = (np.sign(num) * (np.abs(num) // max_abs)).astype(np.int32)
            scale_factor = FUSION_FULL_SCALE / max_abs

        # WAV 파일 쓰기 (32-bit, 동적 샘플레이트)
        with wave.open(str(wav_path), 'wb') as wav_file:
            wav_file.setnchannels(OUTPUT_CHANNELS)
            wav_file.setsampwidth(OUTPUT_SAMPLE_WIDTH)  # 4 bytes = 32-bit
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(scaled_data.tobytes())

        ensure_permissions(wav_path, is_directory=False)

        self.logger.debug(
            f"변환 완료: {bid_path.name} → {wav_path.name} "
            f"(max_abs={max_abs:,}, scale={scale_factor:.2f})"
        )

        return max_abs, scale_factor
