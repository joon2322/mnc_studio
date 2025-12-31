"""파서 베이스 클래스"""

from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Callable
import pandas as pd
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import EXPECTED_ROWS, PARQUET_SCHEMA, FREQUENCY_COLUMNS


class BaseParser(ABC):
    """파서 추상 베이스 클래스"""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self._log_callback: Optional[Callable[[str], None]] = None

    def set_log_callback(self, callback: Callable[[str], None]):
        """로그 콜백 설정 (GUI 연동용)"""
        self._log_callback = callback

    @abstractmethod
    def detect(self, folder_path: Path) -> bool:
        """해당 장비 폴더인지 감지"""
        pass

    @abstractmethod
    def process(self, device_folder: Path, weighting: str = 'LAS',
                include_bands: bool = True) -> Dict[str, pd.DataFrame]:
        """
        장비 데이터 처리

        Args:
            device_folder: 장비 폴더 경로
            weighting: 가중치 ('LAS' 또는 'LCS')
            include_bands: 주파수 밴드 포함 여부

        Returns:
            {날짜문자열: DataFrame} 딕셔너리
        """
        pass

    def create_full_day_df(self, date: datetime, include_bands: bool = True) -> pd.DataFrame:
        """
        86,400행 DataFrame 생성 (NaN 초기화)

        Args:
            date: 기준 날짜
            include_bands: 주파수 밴드 포함 여부

        Returns:
            86,400행 DataFrame (00:00:00 ~ 23:59:59)
        """
        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        timestamps = [start + timedelta(seconds=i) for i in range(EXPECTED_ROWS)]

        data = {'timestamp': timestamps, 'spl': np.nan}

        if include_bands:
            for col in FREQUENCY_COLUMNS:
                data[col] = np.nan

        return pd.DataFrame(data)

    def log_error(self, message: str):
        """에러 로그"""
        self.errors.append(message)
        log_msg = f"[ERROR] {message}"
        print(log_msg)
        if self._log_callback:
            self._log_callback(log_msg)

    def log_warning(self, message: str):
        """경고 로그"""
        self.warnings.append(message)
        log_msg = f"[WARN] {message}"
        print(log_msg)
        if self._log_callback:
            self._log_callback(log_msg)

    def log_info(self, message: str):
        """정보 로그"""
        log_msg = f"[INFO] {message}"
        print(log_msg)
        if self._log_callback:
            self._log_callback(log_msg)

    def clear_logs(self):
        """로그 초기화"""
        self.errors = []
        self.warnings = []
