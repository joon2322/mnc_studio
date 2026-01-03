"""
Rion 장비 오디오 복사기

Rion WAV 파일은 이미 표준 형식이므로 변환 없이 복사만 수행
"""

import shutil
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, List, Optional

from .base_processor import BaseProcessor, ProcessingResult


@dataclass
class RionProcessResult:
    """Rion 처리 결과 (하위 호환용)"""
    success: bool
    files_processed: int
    files_copied: int
    message: str = ""


class RionProcessor(BaseProcessor):
    """Rion 오디오 복사기"""

    SOUND_FOLDER = 'SOUND'

    def __init__(self, measurement_date: date):
        """
        Args:
            measurement_date: 측정 날짜 (해당 날짜 파일만 복사)
        """
        super().__init__()
        self.measurement_date = measurement_date
        self.date_str = measurement_date.strftime("%Y%m%d")

    def _find_sound_folders(self, input_path: Path) -> List[Path]:
        """
        SOUND 폴더들 찾기 (세 가지 구조 지원)

        구조 A: input_path/Auto_*/SOUND/ (input_path = 장비폴더 NX-42RT)
        구조 B: input_path/Auto/SOUND/   (input_path = 지점폴더)
        구조 C: input_path/SOUND/        (input_path = 지점폴더, SOUND 직접)
        """
        sound_folders = []
        try:
            # 구조 A: Auto_*/SOUND/
            for auto_folder in input_path.glob('Auto_*'):
                if auto_folder.is_dir():
                    sound_folder = auto_folder / self.SOUND_FOLDER
                    if sound_folder.exists() and sound_folder.is_dir():
                        sound_folders.append(sound_folder)

            # 구조 B: Auto/SOUND/ (Auto_*가 없는 경우)
            if not sound_folders:
                auto_folder = input_path / 'Auto'
                if auto_folder.is_dir():
                    sound_folder = auto_folder / self.SOUND_FOLDER
                    if sound_folder.exists() and sound_folder.is_dir():
                        sound_folders.append(sound_folder)

            # 구조 C: SOUND/ (SOUND가 직접 있는 경우)
            if not sound_folders:
                sound_folder = input_path / self.SOUND_FOLDER
                if sound_folder.exists() and sound_folder.is_dir():
                    sound_folders.append(sound_folder)
        except PermissionError:
            pass
        return sound_folders

    def _is_target_date(self, filename: str) -> bool:
        """파일명이 대상 날짜인지 확인"""
        return f"_{self.date_str}_" in filename

    def _get_target_wav_files(self, sound_folders: List[Path]) -> List[Path]:
        """대상 날짜의 WAV 파일 목록"""
        wav_files = []
        for sound_folder in sound_folders:
            try:
                for wav_file in sound_folder.glob('*.wav'):
                    if self._is_target_date(wav_file.name):
                        wav_files.append(wav_file)
                for wav_file in sound_folder.glob('*.WAV'):
                    if self._is_target_date(wav_file.name):
                        wav_files.append(wav_file)
            except PermissionError:
                pass
        return sorted(wav_files)

    def get_output_filename(self, input_file: Path) -> str:
        """
        출력 파일명 생성 (BaseProcessor 추상 메서드 구현)

        입력: NL_001_20250819_095300_120dB_0034_0000_ST0001.wav
        출력: 095300_095400.wav (시작시간_종료시간)

        Fusion과 동일한 형식으로 정규화
        """
        filename = input_file.name

        # 시간 추출: NL_001_20250819_HHMMSS_...
        match = re.search(r'_\d{8}_(\d{6})_', filename)
        if match:
            start_time = match.group(1)
            # 1분 단위로 가정 (Rion은 보통 1분 녹음)
            # HHMMSS → HH:MM:SS + 1분
            h, m, s = int(start_time[:2]), int(start_time[2:4]), int(start_time[4:6])
            end_m = m + 1
            end_h = h
            if end_m >= 60:
                end_m = 0
                end_h += 1
            if end_h >= 24:
                end_h = 0
            end_time = f"{end_h:02d}{end_m:02d}{s:02d}"
            return f"{start_time}_{end_time}.wav"

        # 파싱 실패 시 원본 파일명 사용
        return filename

    def process(
        self,
        input_path: Path,
        output_path: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> ProcessingResult:
        """
        Rion WAV 파일 복사 (BaseProcessor 추상 메서드 구현)

        Args:
            input_path: 장비 폴더 경로 (예: .../NX-42RT/)
            output_path: 출력 폴더 경로 (세션 폴더)
            progress_callback: 진행 콜백 (current, total, message)

        Returns:
            ProcessingResult
        """
        # SOUND 폴더 찾기
        sound_folders = self._find_sound_folders(input_path)
        if not sound_folders:
            return ProcessingResult(
                success=False,
                input_path=input_path,
                output_path=output_path,
                message="SOUND 폴더 없음",
                files_processed=0,
                files_failed=0,
            )

        # 대상 날짜 WAV 파일 수집
        wav_files = self._get_target_wav_files(sound_folders)
        if not wav_files:
            return ProcessingResult(
                success=False,
                input_path=input_path,
                output_path=output_path,
                message=f"{self.date_str} 날짜의 WAV 파일 없음",
                files_processed=0,
                files_failed=0,
            )

        # 출력 폴더 확인
        output_path.mkdir(parents=True, exist_ok=True)

        # 파일 복사
        copied_count = 0
        errors = []
        total_files = len(wav_files)

        for i, wav_file in enumerate(wav_files):
            try:
                output_filename = self.get_output_filename(wav_file)
                output_file = output_path / output_filename

                # 진행 콜백
                if progress_callback:
                    progress_callback(i + 1, total_files, wav_file.name)

                # 이미 존재하면 스킵
                if output_file.exists():
                    copied_count += 1
                    continue

                # 복사
                shutil.copy2(wav_file, output_file)
                copied_count += 1

            except Exception as e:
                errors.append(f"{wav_file.name}: {e}")

        if errors:
            return ProcessingResult(
                success=False,
                input_path=input_path,
                output_path=output_path,
                message=f"일부 실패: {errors[:3]}",
                files_processed=copied_count,
                files_failed=len(errors),
                errors=errors,
            )

        return ProcessingResult(
            success=True,
            input_path=input_path,
            output_path=output_path,
            message=f"{copied_count}개 파일 복사 완료",
            files_processed=copied_count,
            files_failed=0,
        )

    def process_legacy(self, source_path: Path, output_path: Path) -> RionProcessResult:
        """
        하위 호환용 레거시 인터페이스

        Args:
            source_path: 장비 폴더 경로
            output_path: 출력 폴더 경로

        Returns:
            RionProcessResult
        """
        result = self.process(source_path, output_path)
        return RionProcessResult(
            success=result.success,
            files_processed=result.files_processed,
            files_copied=result.files_processed - result.files_failed,
            message=result.message,
        )
