"""파서 베이스 클래스"""

import logging
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from ..config import SECONDS_PER_DAY, FREQUENCY_BANDS

logger = logging.getLogger(__name__)


class BaseParser(ABC):
    """파서 베이스 클래스"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def create_full_day_dataframe(
        self,
        measurement_date: date,
        include_bands: bool = True
    ) -> pd.DataFrame:
        """
        86,400행의 빈 DataFrame 생성

        Args:
            measurement_date: 측정일
            include_bands: 주파수 밴드 포함 여부

        Returns:
            timestamp, spl, (밴드) 컬럼을 가진 DataFrame
        """
        # 자정부터 시작하는 타임스탬프 생성
        start = datetime.combine(measurement_date, datetime.min.time())
        timestamps = [start + timedelta(seconds=i) for i in range(SECONDS_PER_DAY)]

        # 기본 컬럼
        data = {
            'timestamp': timestamps,
            'spl': np.nan,
        }

        # 주파수 밴드 컬럼 추가
        if include_bands:
            for band in FREQUENCY_BANDS:
                data[band] = np.nan

        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        return df

    @abstractmethod
    def parse(
        self,
        input_path: Path,
        measurement_date: date,
        weighting: str = 'LAS'
    ) -> pd.DataFrame:
        """
        데이터 파싱

        Args:
            input_path: 입력 경로 (파일 또는 폴더)
            measurement_date: 측정일
            weighting: 가중치 (LAS 또는 LCS)

        Returns:
            86,400행의 DataFrame
        """
        pass

    @abstractmethod
    def detect_sessions(self, root_path: Path) -> list:
        """
        세션 감지

        Args:
            root_path: 검색 루트 경로

        Returns:
            감지된 세션 목록
        """
        pass
