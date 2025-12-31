"""Audio Copier 설정"""

from pathlib import Path

# 앱 정보
APP_NAME = "MNC Audio Copier"
APP_VERSION = "1.0.0"

# 기본 경로
DEFAULT_SOURCE_BASE = Path("/mnt/audio_archive/raw_audio")
DEFAULT_OUTPUT_BASE = Path("/mnt/audio_archive/copy_output")

# 파일 확장자
WAV_EXTENSION = "*.wav"

# 한글 요일
WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]

# 권한
DIR_PERMISSION = 0o755
FILE_PERMISSION = 0o644
