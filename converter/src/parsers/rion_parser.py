"""Rion 파서 (.rnd 파일)"""

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

import pandas as pd

from ..config import RION_ENCODINGS, SECONDS_PER_DAY
from ..utils.round_utils import round_half_up
from .base_parser import BaseParser

logger = logging.getLogger(__name__)


@dataclass
class RionSession:
    """Rion 세션 정보"""
    point: str
    measurement_date: date
    source_path: Path
    rnd_files: List[Path]


class RionParser(BaseParser):
    """Rion .rnd 파서"""

    def __init__(self):
        super().__init__()

    def parse(
        self,
        input_path: Path,
        measurement_date: date,
        weighting: str = 'LAS'
    ) -> pd.DataFrame:
        """
        Rion .rnd 파일 파싱

        Args:
            input_path: .rnd 파일 경로 또는 폴더
            measurement_date: 측정일
            weighting: 가중치 (LAS 또는 LCS)

        Returns:
            86,400행의 DataFrame
        """
        # 빈 DataFrame 생성
        df = self.create_full_day_dataframe(measurement_date, include_bands=False)

        # 파일 목록 수집
        if input_path.is_file():
            rnd_files = [input_path]
        else:
            # AUTO_LP 폴더 우선 검색
            auto_lp = input_path / "AUTO_LP"
            if auto_lp.exists():
                rnd_files = sorted(auto_lp.glob("*.rnd"))
            else:
                rnd_files = sorted(input_path.glob("*.rnd"))

        if not rnd_files:
            self.logger.warning(f"RND 파일 없음: {input_path}")
            return df

        # 각 파일 처리
        for rnd_file in rnd_files:
            try:
                file_df = self._read_rnd_file(rnd_file, weighting)
                if file_df is not None:
                    # 데이터 병합
                    for _, row in file_df.iterrows():
                        ts = row['timestamp']
                        # 해당 날짜만 처리
                        if ts.date() == measurement_date:
                            idx = ts.hour * 3600 + ts.minute * 60 + ts.second
                            if 0 <= idx < SECONDS_PER_DAY:
                                df.at[idx, 'spl'] = row['spl']

            except Exception as e:
                self.logger.error(f"RND 파싱 실패: {rnd_file} - {e}")

        return df

    def _read_rnd_file(
        self,
        file_path: Path,
        weighting: str
    ) -> Optional[pd.DataFrame]:
        """
        단일 .rnd 파일 읽기

        Args:
            file_path: .rnd 파일 경로
            weighting: LAS 또는 LCS

        Returns:
            DataFrame (timestamp, spl)
        """
        # 인코딩 시도
        raw_df = None
        for encoding in RION_ENCODINGS:
            try:
                raw_df = pd.read_csv(
                    file_path,
                    skiprows=1,  # 헤더 스킵
                    encoding=encoding
                )
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                self.logger.warning(f"읽기 실패 ({encoding}): {file_path} - {e}")
                continue

        if raw_df is None or raw_df.empty:
            return None

        # 컬럼 매핑
        # Rion 파일 형식: Start Time, Main, Sub, ...
        result = pd.DataFrame()

        if 'Start Time' in raw_df.columns:
            result['timestamp'] = pd.to_datetime(raw_df['Start Time']).dt.floor('s')
        else:
            # 첫 번째 컬럼이 시간일 수 있음
            result['timestamp'] = pd.to_datetime(raw_df.iloc[:, 0]).dt.floor('s')

        # 가중치에 따른 컬럼 선택
        if weighting == 'LAS':
            if 'Main' in raw_df.columns:
                result['spl'] = raw_df['Main'].apply(lambda x: round_half_up(float(x), 1))
            elif len(raw_df.columns) > 1:
                result['spl'] = raw_df.iloc[:, 1].apply(lambda x: round_half_up(float(x), 1))
        else:  # LCS
            if 'Sub' in raw_df.columns:
                result['spl'] = raw_df['Sub'].apply(lambda x: round_half_up(float(x), 1))
            elif len(raw_df.columns) > 2:
                result['spl'] = raw_df.iloc[:, 2].apply(lambda x: round_half_up(float(x), 1))

        return result

    def detect_sessions(self, root_path: Path) -> List[RionSession]:
        """
        루트 경로에서 Rion 세션 감지

        Args:
            root_path: 검색 루트 경로

        Returns:
            감지된 RionSession 리스트
        """
        sessions = []
        self._find_sessions_recursive(root_path, sessions, depth=0, max_depth=5)

        sessions.sort(key=lambda s: (s.point, s.measurement_date))

        self.logger.info(f"감지된 Rion 세션: {len(sessions)}개")
        return sessions

    def _find_sessions_recursive(
        self,
        path: Path,
        sessions: List[RionSession],
        depth: int,
        max_depth: int,
        point: str = ""
    ):
        """재귀적 세션 탐색"""
        if depth > max_depth:
            return

        if not path.is_dir():
            return

        folder_name = path.name

        # 지점 폴더인지 확인
        if self._is_point_folder(folder_name):
            point = self._normalize_point(folder_name)

        # AUTO_LP 폴더 확인
        auto_lp = path / "AUTO_LP"
        if auto_lp.exists():
            rnd_files = list(auto_lp.glob("*.rnd"))
            if rnd_files and point:
                # 첫 번째 파일에서 날짜 추출
                measurement_date = self._extract_date_from_rnd(rnd_files[0])
                if measurement_date:
                    session = RionSession(
                        point=point,
                        measurement_date=measurement_date,
                        source_path=path,
                        rnd_files=rnd_files
                    )
                    sessions.append(session)
            return

        # 하위 탐색
        try:
            for child in path.iterdir():
                if child.is_dir():
                    self._find_sessions_recursive(
                        child, sessions, depth + 1, max_depth, point
                    )
        except PermissionError:
            pass

    def _is_point_folder(self, name: str) -> bool:
        """지점 폴더 패턴 확인"""
        return bool(re.match(r'^(N-?\d+|이동식)', name, re.IGNORECASE))

    def _normalize_point(self, folder_name: str) -> str:
        """지점명 정규화"""
        name = folder_name.strip()

        match = re.match(r'^이동식\s*N?0*(\d+)', name, re.IGNORECASE)
        if match:
            return f"이동식{int(match.group(1))}"

        match = re.match(r'^N-?0*(\d+)', name, re.IGNORECASE)
        if match:
            return f"N-{int(match.group(1))}"

        return name.split()[0] if ' ' in name else name

    def _extract_date_from_rnd(self, file_path: Path) -> Optional[date]:
        """RND 파일에서 날짜 추출"""
        try:
            for encoding in RION_ENCODINGS:
                try:
                    df = pd.read_csv(file_path, skiprows=1, encoding=encoding, nrows=1)
                    if 'Start Time' in df.columns:
                        ts = pd.to_datetime(df['Start Time'].iloc[0])
                        return ts.date()
                    break
                except UnicodeDecodeError:
                    continue
        except Exception:
            pass
        return None
