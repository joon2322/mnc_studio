"""Fusion 파서 (LASeq.bid, LCSeq.bid)"""

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd

from ..config import FUSION_BID_DTYPE, FUSION_BID_SCALE, SECONDS_PER_DAY
from ..utils.round_utils import round_half_up
from .base_parser import BaseParser

logger = logging.getLogger(__name__)


@dataclass
class FusionSession:
    """Fusion 세션 정보"""
    point: str
    equipment_serial: str
    measurement_date: date
    source_path: Path
    bid_file: Optional[Path] = None


class FusionParser(BaseParser):
    """Fusion LASeq/LCSeq BID 파서"""

    def __init__(self):
        super().__init__()

    def parse(
        self,
        input_path: Path,
        measurement_date: date,
        weighting: str = 'LAS'
    ) -> pd.DataFrame:
        """
        Fusion 세션 폴더의 BID 데이터 파싱

        Args:
            input_path: 세션 폴더 (YYYYMMDD_HHMMSS_HHMMSS)
            measurement_date: 측정일
            weighting: 가중치 (LAS 또는 LCS)

        Returns:
            86,400행의 DataFrame
        """
        # 빈 DataFrame 생성
        df = self.create_full_day_dataframe(measurement_date, include_bands=False)

        # BID 파일 찾기
        bid_filename = f"{weighting}eq.bid"
        bid_file = input_path / bid_filename

        if not bid_file.exists():
            # 대소문자 무시 검색
            for f in input_path.glob("*.bid"):
                if f.name.lower() == bid_filename.lower():
                    bid_file = f
                    break

        if not bid_file.exists():
            self.logger.warning(f"BID 파일 없음: {bid_file}")
            return df

        # BID 파일 읽기
        try:
            raw_data = np.fromfile(bid_file, dtype=FUSION_BID_DTYPE)
            db_values = raw_data.astype(float) / FUSION_BID_SCALE

            # 세션 시작 시간 파싱
            start_second = self._parse_session_start(input_path.name)

            # 데이터 채우기
            for i, db in enumerate(db_values):
                idx = start_second + i
                if 0 <= idx < SECONDS_PER_DAY:
                    df.at[idx, 'spl'] = round_half_up(db, 1)

            self.logger.info(
                f"파싱 완료: {bid_file.name}, {len(db_values)}개 샘플"
            )

        except Exception as e:
            self.logger.error(f"BID 파싱 실패: {bid_file} - {e}")

        return df

    def _parse_session_start(self, folder_name: str) -> int:
        """
        세션 폴더명에서 시작 시간(초) 추출

        형식: YYYYMMDD_HHMMSS_HHMMSS
        예: 20251204_115306_235306 → 11*3600 + 53*60 + 6 = 42786

        Returns:
            시작 시간 (초), 파싱 실패 시 0
        """
        match = re.match(r'^\d{8}_(\d{2})(\d{2})(\d{2})_\d{6}$', folder_name)
        if match:
            h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return h * 3600 + m * 60 + s
        return 0

    def detect_sessions(self, root_path: Path) -> List[FusionSession]:
        """
        루트 경로에서 Fusion 세션 감지

        탐색 구조 (5레벨):
        root/지점/장비시리얼/세션폴더/
        root/지점/세션폴더/
        root/기타폴더/.../세션폴더/

        Args:
            root_path: 검색 루트 경로

        Returns:
            감지된 FusionSession 리스트
        """
        sessions = []
        self._find_sessions_recursive(root_path, sessions, depth=0, max_depth=5)

        # 정렬
        sessions.sort(key=lambda s: (s.point, s.measurement_date))

        self.logger.info(f"감지된 세션: {len(sessions)}개")
        return sessions

    def _find_sessions_recursive(
        self,
        path: Path,
        sessions: List[FusionSession],
        depth: int,
        max_depth: int,
        point: str = "",
        equipment: str = ""
    ):
        """재귀적 세션 탐색"""
        if depth > max_depth:
            return

        if not path.is_dir():
            return

        folder_name = path.name

        # 세션 폴더인지 확인 (YYYYMMDD_HHMMSS_HHMMSS)
        if self._is_session_folder(folder_name):
            measurement_date = self._parse_session_date(folder_name)
            if measurement_date and point:
                session = FusionSession(
                    point=point,
                    equipment_serial=equipment,
                    measurement_date=measurement_date,
                    source_path=path
                )
                sessions.append(session)
            return

        # 지점 폴더인지 확인
        if self._is_point_folder(folder_name):
            point = self._normalize_point(folder_name)

        # 장비 시리얼인지 확인
        if self._is_equipment_serial(folder_name):
            equipment = folder_name

        # 하위 탐색
        try:
            for child in path.iterdir():
                if child.is_dir():
                    self._find_sessions_recursive(
                        child, sessions, depth + 1, max_depth, point, equipment
                    )
        except PermissionError:
            pass

    def _is_session_folder(self, name: str) -> bool:
        """세션 폴더 패턴 확인 (YYYYMMDD_HHMMSS_HHMMSS)"""
        return bool(re.match(r'^\d{8}_\d{6}_\d{6}$', name))

    def _is_point_folder(self, name: str) -> bool:
        """지점 폴더 패턴 확인 (N-1, N01, 이동식 등)"""
        # 장비 시리얼이면 제외
        if self._is_equipment_serial(name):
            return False
        # N으로 시작하거나 이동식
        return bool(re.match(r'^(N-?\d+|이동식)', name, re.IGNORECASE))

    def _is_equipment_serial(self, name: str) -> bool:
        """장비 시리얼 패턴 확인 (N2xx, N3xx, N4xx, N5xx)"""
        return bool(re.match(r'^N[2-5]\d{2}$', name, re.IGNORECASE))

    def _normalize_point(self, folder_name: str) -> str:
        """지점명 정규화"""
        name = folder_name.strip()

        # 이동식 패턴
        match = re.match(r'^이동식\s*N?0*(\d+)', name, re.IGNORECASE)
        if match:
            return f"이동식{int(match.group(1))}"

        # N 패턴
        match = re.match(r'^N-?0*(\d+)', name, re.IGNORECASE)
        if match:
            return f"N-{int(match.group(1))}"

        return name.split()[0] if ' ' in name else name

    def _parse_session_date(self, folder_name: str) -> Optional[date]:
        """세션 폴더명에서 날짜 추출"""
        match = re.match(r'^(\d{8})_\d{6}_\d{6}$', folder_name)
        if match:
            try:
                return datetime.strptime(match.group(1), "%Y%m%d").date()
            except ValueError:
                pass
        return None
