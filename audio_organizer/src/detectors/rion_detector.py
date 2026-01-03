"""
Rion 장비 오디오 감지기

지원 장비: NX-42RT, NL-* 시리즈
지원 폴더 구조:
  - 구조 A: 지점폴더/NX-42RT/Auto_*/SOUND/*.wav (수원)
  - 구조 B: 지점폴더/Auto/SOUND/*.wav (오산 이동식 N-1)
  - 구조 C: 지점폴더/SOUND/*.wav (오산 이동식 N-2~N-6 - SOUND 직접)
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Optional, Tuple
import re

from .base_detector import BaseDetector, AudioSession
from ..utils.point_utils import normalize_point_name


@dataclass
class RionSession(AudioSession):
    """Rion 오디오 세션 정보"""
    device_model: str = ""  # NX-42RT, NL 등


class RionDetector(BaseDetector):
    """Rion 장비 오디오 감지기"""

    # 지원 장비 모델 접두사
    DEVICE_PREFIXES = ['NX-', 'NL-']

    # SOUND 폴더명
    SOUND_FOLDER = 'SOUND'

    def detect(self, source_path: Path) -> bool:
        """
        Rion 장비 폴더 감지

        두 가지 구조 지원:
        - 구조 A: 지점/NX-*/Auto_*/SOUND/
        - 구조 B: 지점/Auto/SOUND/ (NL_ 파일명)

        Args:
            source_path: 소스 폴더 경로

        Returns:
            Rion 장비 폴더가 있으면 True
        """
        try:
            for point_dir in source_path.iterdir():
                if not point_dir.is_dir():
                    continue

                # 구조 A: NX-*, NL-* 장비 폴더 확인
                for child in point_dir.iterdir():
                    if child.is_dir():
                        if any(child.name.startswith(p) for p in self.DEVICE_PREFIXES):
                            return True

                # 구조 B: Auto/SOUND 직접 확인
                auto_folder = point_dir / 'Auto'
                if auto_folder.is_dir():
                    sound_folder = auto_folder / self.SOUND_FOLDER
                    if sound_folder.is_dir():
                        # NL_ 파일 있는지 확인
                        for wav in sound_folder.glob('*.wav'):
                            if wav.name.startswith('NL_'):
                                return True
                        for wav in sound_folder.glob('*.WAV'):
                            if wav.name.upper().startswith('NL_'):
                                return True

                # 구조 C: SOUND가 지점폴더 바로 아래
                sound_folder = point_dir / self.SOUND_FOLDER
                if sound_folder.is_dir():
                    for wav in sound_folder.glob('*.wav'):
                        if wav.name.startswith('NL_'):
                            return True
                    for wav in sound_folder.glob('*.WAV'):
                        if wav.name.upper().startswith('NL_'):
                            return True
        except PermissionError:
            pass
        return False

    def _find_device_folder(self, point_dir: Path) -> Optional[Path]:
        """지점 폴더 내 장비 폴더 찾기 (구조 A용)"""
        try:
            for child in point_dir.iterdir():
                if child.is_dir():
                    if any(child.name.startswith(p) for p in self.DEVICE_PREFIXES):
                        return child
        except PermissionError:
            pass
        return None

    def _find_sound_folders_structure_a(self, device_folder: Path) -> List[Path]:
        """
        구조 A: 장비 폴더 내 SOUND 폴더들 찾기
        구조: device_folder/Auto_*/SOUND/
        """
        sound_folders = []
        try:
            for auto_folder in device_folder.glob('Auto_*'):
                if auto_folder.is_dir():
                    sound_folder = auto_folder / self.SOUND_FOLDER
                    if sound_folder.exists() and sound_folder.is_dir():
                        sound_folders.append(sound_folder)
        except PermissionError:
            pass
        return sound_folders

    def _find_sound_folders_structure_b(self, point_dir: Path) -> List[Path]:
        """
        구조 B: 지점 폴더 내 Auto/SOUND 찾기
        구조: point_dir/Auto/SOUND/
        """
        sound_folders = []
        try:
            auto_folder = point_dir / 'Auto'
            if auto_folder.is_dir():
                sound_folder = auto_folder / self.SOUND_FOLDER
                if sound_folder.exists() and sound_folder.is_dir():
                    sound_folders.append(sound_folder)
        except PermissionError:
            pass
        return sound_folders

    def _find_sound_folders_structure_c(self, point_dir: Path) -> List[Path]:
        """
        구조 C: 지점 폴더 내 SOUND 직접 찾기
        구조: point_dir/SOUND/
        """
        sound_folders = []
        try:
            sound_folder = point_dir / self.SOUND_FOLDER
            if sound_folder.exists() and sound_folder.is_dir():
                sound_folders.append(sound_folder)
        except PermissionError:
            pass
        return sound_folders

    def _parse_wav_filename(self, filename: str) -> Optional[date]:
        """
        WAV 파일명에서 날짜 추출

        형식: NL_001_20250819_095300_120dB_0034_0000_ST0001.wav
                     ^^^^^^^^ 날짜
        """
        # YYYYMMDD 패턴 찾기
        match = re.search(r'_(\d{8})_', filename)
        if match:
            date_str = match.group(1)
            try:
                return date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
            except ValueError:
                pass
        return None

    def _extract_device_model(self, wav_files: List[Path]) -> str:
        """WAV 파일명에서 장비 모델 추출"""
        if not wav_files:
            return "Unknown"

        filename = wav_files[0].name
        # NL_001_... → NL
        if filename.startswith('NL_'):
            return "NL"
        # NX-42RT 형식 등
        match = re.match(r'^(N[XL]-?\w+)', filename)
        if match:
            return match.group(1)
        return "Rion"

    def _get_wav_files(self, sound_folders: List[Path]) -> List[Path]:
        """SOUND 폴더들에서 WAV 파일 목록 가져오기"""
        wav_files = []
        for sound_folder in sound_folders:
            try:
                wav_files.extend(sound_folder.glob('*.wav'))
                wav_files.extend(sound_folder.glob('*.WAV'))
            except PermissionError:
                pass
        return wav_files

    def _extract_point_name(self, point_dir: Path) -> str:
        """폴더명에서 지점명 추출 (공통 유틸리티 사용)"""
        return normalize_point_name(point_dir.name)

    def extract_point(self, folder_path: Path) -> Optional[str]:
        """
        폴더 경로에서 지점명 추출 (BaseDetector 추상 메서드 구현)

        Args:
            folder_path: 폴더 경로 (지점 폴더 또는 하위 폴더)

        Returns:
            정규화된 지점명 또는 None
        """
        # 지점 폴더인 경우 (구조 A or B)
        if self._find_device_folder(folder_path) or (folder_path / 'Auto').is_dir():
            return self._extract_point_name(folder_path)

        # 장비 폴더인 경우 (NX-*, NL-*)
        if any(folder_path.name.startswith(p) for p in self.DEVICE_PREFIXES):
            parent = folder_path.parent
            return self._extract_point_name(parent)

        # Auto 또는 Auto_* 폴더인 경우
        if folder_path.name == 'Auto' or folder_path.name.startswith('Auto_'):
            parent = folder_path.parent
            # 구조 A: Auto_* → 장비폴더 → 지점
            if any(parent.name.startswith(p) for p in self.DEVICE_PREFIXES):
                return self._extract_point_name(parent.parent)
            # 구조 B: Auto → 지점
            return self._extract_point_name(parent)

        return None

    def _scan_point(self, point_dir: Path) -> Tuple[List[Path], str, Path]:
        """
        지점 폴더 스캔 (세 가지 구조 모두 처리)

        Returns:
            (sound_folders, device_model, source_path) 또는 ([], "", None)
        """
        # 구조 A: NX-*/NL-* 장비 폴더가 있는 경우
        device_folder = self._find_device_folder(point_dir)
        if device_folder:
            sound_folders = self._find_sound_folders_structure_a(device_folder)
            if sound_folders:
                return sound_folders, device_folder.name, device_folder

        # 구조 B: Auto/SOUND가 있는 경우
        sound_folders = self._find_sound_folders_structure_b(point_dir)
        if sound_folders:
            wav_files = self._get_wav_files(sound_folders)
            nl_files = [f for f in wav_files if f.name.startswith('NL_') or f.name.upper().startswith('NL_')]
            if nl_files:
                device_model = self._extract_device_model(nl_files)
                return sound_folders, device_model, point_dir

        # 구조 C: SOUND가 지점폴더 바로 아래 있는 경우
        sound_folders = self._find_sound_folders_structure_c(point_dir)
        if sound_folders:
            wav_files = self._get_wav_files(sound_folders)
            nl_files = [f for f in wav_files if f.name.startswith('NL_') or f.name.upper().startswith('NL_')]
            if nl_files:
                device_model = self._extract_device_model(nl_files)
                return sound_folders, device_model, point_dir

        return [], "", None

    def scan(self, source_path: Path) -> List[RionSession]:
        """
        Rion 세션 스캔

        Args:
            source_path: 소스 폴더 경로

        Returns:
            RionSession 목록
        """
        sessions = []

        try:
            for point_dir in sorted(source_path.iterdir()):
                if not point_dir.is_dir():
                    continue

                # 두 구조 모두 처리
                sound_folders, device_model, session_source = self._scan_point(point_dir)
                if not sound_folders or session_source is None:
                    continue

                # WAV 파일 수집
                wav_files = self._get_wav_files(sound_folders)
                if not wav_files:
                    continue

                # 날짜별로 그룹화
                dates_files = {}
                for wav_file in wav_files:
                    file_date = self._parse_wav_filename(wav_file.name)
                    if file_date:
                        if file_date not in dates_files:
                            dates_files[file_date] = []
                        dates_files[file_date].append(wav_file)

                # 세션 생성
                point_name = self._extract_point_name(point_dir)

                for mdate, files in dates_files.items():
                    session = RionSession(
                        point=point_name,
                        equipment_type="rion",
                        measurement_date=mdate,
                        source_path=session_source,
                        file_count=len(files),
                        expected_count=0,  # Rion은 예상 파일 수 없음
                        sample_rate=48000,  # Rion 기본 샘플레이트
                        skip_count=0,
                        device_model=device_model,
                    )
                    sessions.append(session)

        except PermissionError:
            pass

        # 정렬
        sessions.sort(key=lambda s: (s.point, s.measurement_date))
        return sessions
