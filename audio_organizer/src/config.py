"""MNC Audio Organizer 설정 상수"""

from pathlib import Path

# ===== 버전 =====
VERSION = "1.1.0"
APP_VERSION = VERSION  # app.py 호환
APP_NAME = "MNC Audio Organizer"

# ===== Fusion 오디오 설정 =====
FUSION_SAMPLE_RATE = 25600          # Hz
FUSION_BIT_DEPTH = 32               # bits (출력 WAV)
FUSION_BITS_PER_SAMPLE = 32         # bits (출력 WAV, alias)
FUSION_CHANNELS = 1                 # mono
FUSION_BID_BYTES_PER_SAMPLE = 4     # BID 파일은 32-bit (4 bytes)
FUSION_WAV_BYTES_PER_SAMPLE = 4     # WAV 출력은 32-bit (4 bytes)

# ===== 피크 정규화 상수 =====
# 정식 Fusion 프로그램 동일값 (INT32_MAX - 5)
# 검증: 미여도, 낙동, 수원 데이터에서 100% 샘플 일치 확인
FUSION_FULL_SCALE = 2_147_483_642
FUSION_SEGMENT_DURATION = 30 * 60   # 30분 = 1800초

# ===== WAV 출력 설정 =====
OUTPUT_CHANNELS = 1                  # mono
OUTPUT_SAMPLE_WIDTH = 4              # 32-bit = 4 bytes (정식 프로그램 동일)
FUSION_EXPECTED_FILE_SIZE = FUSION_SAMPLE_RATE * FUSION_SEGMENT_DURATION * FUSION_BID_BYTES_PER_SAMPLE  # 184,320,000 bytes
FUSION_EXPECTED_SAMPLES = FUSION_SAMPLE_RATE * FUSION_SEGMENT_DURATION  # 46,080,000 samples

# ===== 복사/변환 설정 =====
COPY_MAX_RETRY = 3                  # 최대 재시도 횟수
COPY_RETRY_DELAY = 1.0              # 재시도 간 딜레이 (초)

# ===== 검증 설정 =====
SAMPLE_TOLERANCE = FUSION_SAMPLE_RATE  # 허용 오차: ±1초 (25600 샘플)
WAV_HEADER_MIN_SIZE = 44            # WAV 헤더 최소 크기

# ===== 경로 설정 =====
DEFAULT_OUTPUT_DIR = Path.home() / "audio_organized"
DEFAULT_OUTPUT_BASE = Path("/mnt/audio_archive/raw_audio")  # app.py 호환
UPLOAD_DROP_PATH = Path("/mnt/audio_archive/upload_drop")
EXTERNAL_MOUNT_PATH = Path("/media/joonwon")

# ===== 권한 설정 =====
DIR_PERMISSION = 0o2775             # setgid 포함
FILE_PERMISSION = 0o0664            # 그룹 쓰기 허용

# ===== manifest 설정 =====
MANIFEST_VERSION = "2.0"
MANIFEST_FILENAME = "manifest.json"

# ===== 장비 감지 패턴 =====
FUSION_FOLDER_SUFFIX = "_fusion"
RION_FOLDER_SUFFIX = "_rion"
RION_DEVICE_PREFIXES = ['NL-', 'NX-']
FUSION_AUDIO_FOLDER = "Audio"
RION_SOUND_FOLDER = "SOUND"

# ===== 파일 확장자 =====
BID_EXTENSION = ".bid"
WAV_EXTENSION = ".wav"
WAV_EXTENSIONS = {".wav", ".WAV"}
AUDIO_BID_PATTERN = "*.bid"          # Audio 폴더 BID 패턴

# ===== 한글 요일 =====
WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]

# ===== 로깅 설정 =====
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
