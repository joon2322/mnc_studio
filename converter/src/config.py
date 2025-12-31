"""설정 관리"""

from dataclasses import dataclass
from typing import Optional, List
from pathlib import Path

# 상수
EXPECTED_ROWS = 86400  # 하루 = 24시간 * 60분 * 60초
APP_VERSION = "3.0.0"

# Parquet 스키마 (35컬럼)
PARQUET_SCHEMA = {
    'timestamp': 'datetime64[ns]',
    'spl': 'float64',
    '12.5Hz': 'float64',
    '16Hz': 'float64',
    '20Hz': 'float64',
    '25Hz': 'float64',
    '31.5Hz': 'float64',
    '40Hz': 'float64',
    '50Hz': 'float64',
    '63Hz': 'float64',
    '80Hz': 'float64',
    '100Hz': 'float64',
    '125Hz': 'float64',
    '160Hz': 'float64',
    '200Hz': 'float64',
    '250Hz': 'float64',
    '315Hz': 'float64',
    '400Hz': 'float64',
    '500Hz': 'float64',
    '630Hz': 'float64',
    '800Hz': 'float64',
    '1000Hz': 'float64',
    '1250Hz': 'float64',
    '1600Hz': 'float64',
    '2000Hz': 'float64',
    '2500Hz': 'float64',
    '3150Hz': 'float64',
    '4000Hz': 'float64',
    '5000Hz': 'float64',
    '6300Hz': 'float64',
    '8000Hz': 'float64',
    '10000Hz': 'float64',
    '12500Hz': 'float64',
    '16000Hz': 'float64',
    '20000Hz': 'float64',
}

# 주파수 밴드 컬럼 목록 (33개)
FREQUENCY_COLUMNS = [col for col in PARQUET_SCHEMA.keys() if col not in ['timestamp', 'spl']]


@dataclass
class ConversionConfig:
    """변환 설정"""
    source_path: Path
    output_path: Path
    site_name: str
    round_number: Optional[str] = None  # 차수 (예: "1차")
    weighting: str = 'LAS'              # 가중치 ('LAS', 'LCS', 'both')
    include_bands: bool = True          # 주파수 밴드 포함 여부
    output_csv: bool = True             # CSV 함께 출력

    def __post_init__(self):
        self.source_path = Path(self.source_path)
        self.output_path = Path(self.output_path)
