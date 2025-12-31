"""Fusion 장비 감지"""

import logging
import re
from pathlib import Path
from typing import List, Optional

from .base_detector import BaseDetector, AudioSession
from ..config import (
    FUSION_FOLDER_SUFFIX,
    FUSION_AUDIO_FOLDER,
    BID_EXTENSION,
)
from ..utils.date_utils import parse_fusion_date, parse_fusion_session_duration, calculate_expected_bid_count
from ..validators.fusion_validator import validate_fusion_audio_folder

logger = logging.getLogger(__name__)

# Fusion 장비 시리얼 패턴 (N2xx, N3xx, N4xx, N5xx)
FUSION_SERIAL_PATTERN = re.compile(r'^N[2-5]\d{2}$', re.IGNORECASE)


class FusionDetector(BaseDetector):
    """Fusion 장비 감지 클래스"""

    def _is_serial_folder(self, name: str) -> bool:
        """Fusion 장비 시리얼 폴더인지 확인 (N2xx, N3xx, N4xx, N5xx)"""
        return bool(FUSION_SERIAL_PATTERN.match(name.strip()))

    def _find_session_folders(self, folder_path: Path, max_depth: int = 5) -> List[Path]:
        """
        세션 폴더 찾기 (재귀적으로 최대 max_depth까지 탐색)

        지원 구조 (최대 5단계):
        - folder_path/YYYYMMDD_HHMMSS_HHMMSS/Audio/
        - folder_path/*/YYYYMMDD_HHMMSS_HHMMSS/Audio/
        - folder_path/*/*/YYYYMMDD_HHMMSS_HHMMSS/Audio/
        - 등등...
        """
        session_folders = []
        date_pattern = re.compile(r'^\d{8}_\d{6}_\d{6}$')

        def search_recursive(current_path: Path, depth: int):
            if depth > max_depth:
                return
            try:
                for child in current_path.iterdir():
                    if not child.is_dir():
                        continue
                    # 세션 폴더인 경우 (YYYYMMDD_HHMMSS_HHMMSS)
                    if date_pattern.match(child.name):
                        audio_folder = child / FUSION_AUDIO_FOLDER
                        if audio_folder.exists():
                            session_folders.append(child)
                    else:
                        # 더 깊이 탐색
                        search_recursive(child, depth + 1)
            except PermissionError:
                pass

        search_recursive(folder_path, 0)
        return sorted(session_folders, key=lambda p: p.name)

    def detect(self, folder_path: Path) -> bool:
        """
        Fusion 장비 폴더 감지

        조건:
        1. 폴더명이 *_fusion으로 끝나거나
        2. 하위에 Audio/*.bid 파일이 있거나 (직접 또는 장비 시리얼 폴더 경유)
        3. 하위에 YYYYMMDD_HHMMSS_HHMMSS 형식 폴더가 있음
        """
        if not folder_path.is_dir():
            return False

        # 조건 1: 폴더명
        if folder_path.name.endswith(FUSION_FOLDER_SUFFIX):
            return True

        # 조건 2 & 3: 세션 폴더 찾기 (장비 시리얼 폴더 포함)
        session_folders = self._find_session_folders(folder_path)
        if session_folders:
            # Audio/*.bid 파일 존재 확인
            for session in session_folders:
                audio_folder = session / FUSION_AUDIO_FOLDER
                if audio_folder.exists():
                    bid_files = [
                        f for f in audio_folder.iterdir()
                        if f.is_file() and f.suffix.lower() == BID_EXTENSION.lower()
                    ]
                    if bid_files:
                        return True

        return False

    def _is_equipment_serial(self, name: str) -> bool:
        """
        장비 시리얼 번호인지 확인 (N2xx, N3xx, N4xx, N5xx)

        예: N208, N444, N555 → True (장비 시리얼)
        예: N-01, N-10, N01 → False (지점 번호)
        """
        name_stripped = name.strip()
        # N + 3자리 숫자 (2xx, 3xx, 4xx, 5xx 시리즈)
        return bool(re.match(r'^N[2-5]\d{2}$', name_stripped, re.IGNORECASE))

    def _is_point_folder(self, name: str) -> bool:
        """
        지점 폴더인지 확인 (N-01, N-10, N01 등)

        예: N-01, N-10, N01, N-01_주말에꺼짐 → True (지점)
        예: N208, N444 → False (장비 시리얼)
        """
        # 장비 시리얼이면 제외
        if self._is_equipment_serial(name):
            return False
        # N + 선택적 하이픈 + 1-2자리 숫자로 시작
        return bool(re.match(r'^N-?\d{1,2}(?:\D|$)', name, re.IGNORECASE))

    def extract_point(self, folder_path: Path) -> Optional[str]:
        """
        폴더 경로에서 지점명 추출

        예: /media/.../N-3_fusion → "N-3"
        예: /media/.../N03_fusion → "N-3"
        예: /media/.../N-01 → "N-1"  (원본 데이터 구조)
        예: /media/.../N-01/N208/... → "N-1" (장비시리얼 N208 무시)
        예: /media/.../이동식1_fusion → "이동식1"
        """
        # 현재 폴더명에서 추출
        name = folder_path.name

        # *_fusion 형식
        if name.endswith(FUSION_FOLDER_SUFFIX):
            point_part = name[:-len(FUSION_FOLDER_SUFFIX)]
            return self._normalize_point(point_part)

        # N-01, N-02 등 지점 폴더 형식 (장비 시리얼 제외)
        if self._is_point_folder(name):
            return self._normalize_point(name)

        # 이동식 폴더 형식
        if name.startswith('이동식'):
            return self._normalize_point(name)

        # 상위 폴더에서 시도
        for parent in folder_path.parents:
            parent_name = parent.name
            if parent_name.endswith(FUSION_FOLDER_SUFFIX):
                return self.extract_point(parent)
            # N-01, N-02 등 지점 폴더 형식 (장비 시리얼 제외)
            if self._is_point_folder(parent_name):
                return self._normalize_point(parent_name)
            # 이동식 폴더 형식
            if parent_name.startswith('이동식'):
                return self._normalize_point(parent_name)

        return None

    def _normalize_point(self, raw: str) -> str:
        """
        지점명 정규화

        N03 → N-3, N-03 → N-3, N3 → N-3
        이동식01 → 이동식1, 이동식 N01 → 이동식1
        """
        # 이동식 패턴
        mobile_match = re.match(r'^이동식\s*N?-?0*(\d+)', raw, re.IGNORECASE)
        if mobile_match:
            return f"이동식{mobile_match.group(1)}"

        # N-숫자 패턴 (N03, N-03, N3, N-3 → N-숫자)
        n_match = re.match(r'^N-?0*(\d+)', raw, re.IGNORECASE)
        if n_match:
            return f"N-{n_match.group(1)}"

        return raw

    def scan(self, folder_path: Path) -> List[AudioSession]:
        """
        Fusion 폴더에서 오디오 세션 스캔

        지원 구조 (최대 5단계 깊이):
        - folder_path/**/YYYYMMDD_HHMMSS_HHMMSS/Audio/*.bid
        """
        sessions = []

        try:
            # 세션 폴더 찾기 (재귀 탐색)
            session_folders = self._find_session_folders(folder_path)

            for session_folder in session_folders:
                # 각 세션 폴더의 상위 경로에서 지점명 추출
                point = self.extract_point(session_folder)
                if not point:
                    logger.warning(f"지점명 추출 실패: {session_folder}")
                    continue
                # Audio 폴더 확인
                audio_folder = session_folder / FUSION_AUDIO_FOLDER
                if not audio_folder.exists():
                    continue

                # 측정일 추출
                measurement_date = parse_fusion_date(session_folder.name)
                if not measurement_date:
                    logger.warning(f"측정일 추출 실패: {session_folder.name}")
                    continue

                # .bid 파일 스캔 (대소문자 무시)
                bid_files = [
                    f for f in audio_folder.iterdir()
                    if f.is_file() and f.suffix.lower() == BID_EXTENSION.lower()
                ]
                bid_files.sort(key=lambda f: f.name)

                if not bid_files:
                    continue

                # 용량 계산
                total_bytes = sum(f.stat().st_size for f in bid_files)

                # 예상 파일 수 계산 (부분 세션 감지용)
                expected_count = 0
                duration_sec = parse_fusion_session_duration(session_folder.name)
                if duration_sec:
                    expected_count = calculate_expected_bid_count(duration_sec)

                # 검증
                valid_count, warning_count, skip_count = validate_fusion_audio_folder(audio_folder)

                session = AudioSession(
                    point=point,
                    equipment_type="fusion",
                    measurement_date=measurement_date,
                    source_path=audio_folder,
                    source_files=bid_files,
                    file_count=len(bid_files),
                    total_bytes=total_bytes,
                    expected_count=expected_count,
                    valid_count=valid_count,
                    warning_count=warning_count,
                    skip_count=skip_count,
                )
                sessions.append(session)

                status = session.status
                logger.info(f"Fusion 세션 감지: {point} {measurement_date} ({len(bid_files)}/{expected_count}개 파일) - {status}")

        except PermissionError as e:
            logger.error(f"폴더 접근 실패: {folder_path} - {e}")

        return sessions
