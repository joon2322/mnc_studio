"""Converter 설정 및 상수"""

from pathlib import Path
from typing import Dict

# 앱 정보
APP_NAME = "MNC Master Converter"
APP_VERSION = "3.0.0"

# 기본 경로
DEFAULT_OUTPUT_BASE = Path("/var/mnc_data/work")

# 한글 요일
WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]

# 샘플링 및 파일 설정
SECONDS_PER_DAY = 86400  # 24 * 60 * 60

# Fusion 설정
FUSION_SAMPLE_RATE = 25600
FUSION_BID_DTYPE = '<i2'  # little-endian int16 (LASeq.bid 등)
FUSION_BID_SCALE = 100.0  # dB * 100

# Rion 설정
RION_ENCODINGS = ['utf-8', 'utf-8-sig', 'cp949']

# 가중치 유형
WEIGHTING_TYPES = ['LAS', 'LCS']
DEFAULT_WEIGHTING = 'LAS'

# 1/3 옥타브 밴드 주파수 (33개)
FREQUENCY_BANDS = [
    '12.5Hz', '16Hz', '20Hz', '25Hz', '31.5Hz', '40Hz', '50Hz', '63Hz',
    '80Hz', '100Hz', '125Hz', '160Hz', '200Hz', '250Hz', '315Hz', '400Hz',
    '500Hz', '630Hz', '800Hz', '1000Hz', '1250Hz', '1600Hz', '2000Hz',
    '2500Hz', '3150Hz', '4000Hz', '5000Hz', '6300Hz', '8000Hz', '10000Hz',
    '12500Hz', '16000Hz', '20000Hz'
]

# Parquet 스키마 (35컬럼)
PARQUET_SCHEMA: Dict[str, str] = {
    'timestamp': 'datetime64[ns]',
    'spl': 'float64',
}
# 주파수 밴드 추가
for band in FREQUENCY_BANDS:
    PARQUET_SCHEMA[band] = 'float64'

# 파일 확장자
FUSION_BID_PATTERN = "*.bid"
RION_RND_PATTERN = "*.rnd"
