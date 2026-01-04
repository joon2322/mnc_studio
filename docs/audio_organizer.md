# MNC Audio Organizer v2.0.0

> Fusion/Rion 소음측정기의 오디오 파일을 WAV로 추출하는 CLI 도구

---

## 개요

| 항목 | 값 |
|------|-----|
| **버전** | v2.0.0 |
| **목적** | Fusion BID → WAV 변환, Rion WAV 복사 |
| **인터페이스** | CLI (Command Line) |
| **입력** | Fusion 세션 폴더 (N2xx ~ N5xx), Rion 세션 폴더 (NX-42RT, NL 시리즈) |
| **출력** | 32-bit mono WAV (Fusion), 원본 WAV (Rion) |

---

## v2.0 변경사항

| 변경 | 설명 |
|------|------|
| **Rion 지원** | NX-42RT, NL 시리즈 WAV 파일 복사 (3가지 폴더 구조 지원) |
| **extract-to-main** | 메인시스템 세션 폴더에 직접 추출 (권장 명령어) |
| **계획서/로그 단일화** | `extraction_plan.txt`, `extraction_log.txt` (최신 1개만 유지) |
| **manifest.json 제거** | 세션별 manifest 생성 안 함 |
| **병렬 처리** | 10 workers 기본 (ProcessPoolExecutor) |

---

## 핵심 로직 (절대 변경 금지)

### 1. Fusion BID → WAV 변환 (32-bit 피크 정규화)

**파일**: `src/processors/fusion_processor.py:131-184`

```python
# 정식 Fusion 프로그램과 100% 동일한 알고리즘
FULL_SCALE = 2_147_483_642  # INT32_MAX - 5

raw = np.fromfile(bid_path, dtype='<i4')
raw_64 = raw.astype(np.int64)  # 오버플로우 방지
max_abs = int(np.max(np.abs(raw_64)))

# 정수 나눗셈 (truncation) - 부동소수점 사용 금지!
num = raw_64 * FULL_SCALE
scaled = (np.sign(num) * (np.abs(num) // max_abs)).astype(np.int32)
```

**핵심 규칙**:
- `FULL_SCALE = 2,147,483,642` (INT32_MAX가 아님!)
- 파일별 피크 정규화 (파일마다 max_abs 계산)
- 정수 나눗셈(`//`) 사용 (부동소수점 곱셈 사용 시 LSB 오차 발생)

### 2. Rion WAV 복사

**파일**: `src/processors/rion_processor.py`

```python
# 원본 파일명 그대로 복사 (변환 없음)
shutil.copy2(source_wav, output_path / source_wav.name)
```

**Rion 폴더 구조 지원**:
- 구조 A: `지점/NX-42RT/Auto_*/SOUND/*.wav` (수원 등)
- 구조 B: `지점/Auto/SOUND/*.wav` (오산 이동식 N-1)
- 구조 C: `지점/SOUND/*.wav` (오산 이동식 N-2~N-6)

---

## 사용법

### 스캔
```bash
python main_cli.py scan /path/to/source
```

### 추출 (자체 폴더 구조)
```bash
python main_cli.py extract /path/to/source \
    --location 대구비행장 \
    --output /mnt/audio_archive/raw_audio
```

### 추출 (메인시스템 세션 폴더) - 권장
```bash
python main_cli.py extract-to-main /path/to/source \
    --output /mnt/audio_archive/upload_drop/대구비행장
```

**워크플로우**:
1. 스캔 → 계획서 생성 (`extraction_plan.txt`)
2. 사용자 확인 (y/n)
3. 추출 실행 → 로그 생성 (`extraction_log.txt`)

### 옵션
| 옵션 | 설명 |
|------|------|
| `--include-weekend` | 주말(토/일) 포함 (기본: 제외) |
| `--exclude-partial` | 48개 미만 파일 세션 제외 |
| `--workers N` | 병렬 처리 워커 수 (기본: 10) |
| `--no-color` | 색상 출력 비활성화 |

---

## 출력 파일

### 계획서 (`extraction_plan.txt`)
```
================================================================================
MNC Audio Organizer - 추출 계획서
================================================================================
생성 시간: 2026-01-03 22:42:34
출력 베이스: /mnt/audio_archive/upload_drop/필승사격장

요약
  - Fusion: 30개 (BID → WAV 변환)
  - Rion: 20개 (WAV 복사)

추출 목록
번호  지점    측정일       요일  장비    파일
1     N-1    2025-09-15   월    Fusion  48
2     N-3    2025-09-15   월    Rion    24
...
```

### 로그 (`extraction_log.txt`)
```
================================================================================
MNC Audio Organizer - 추출 로그
================================================================================
시작: 2026-01-03 22:45:00
완료: 2026-01-03 23:07:30
소요: 1350.5초
성공: 50개
실패: 0개

세션별 결과
N-1        2025-09-15 (월) [fusion] -> OK (48 files)
N-3        2025-09-15 (월) [rion] -> OK (24 files)
...
```

---

## 파일 구조

```
audio_organizer/
├── main.py                 # GUI 진입점 (미사용)
├── main_cli.py             # CLI 구현 (주 진입점)
├── src/
│   ├── config.py           # 상수 정의
│   ├── detectors/
│   │   ├── base_detector.py
│   │   ├── fusion_detector.py   # Fusion 세션 감지
│   │   └── rion_detector.py     # Rion 세션 감지 (v2.0)
│   ├── processors/
│   │   ├── base_processor.py
│   │   ├── fusion_processor.py  # BID→WAV 변환
│   │   └── rion_processor.py    # WAV 복사 (v2.0)
│   └── utils/
│       ├── audio_config.py      # 샘플레이트 감지
│       ├── point_utils.py       # 지점명 정규화 (v2.0)
│       ├── permissions.py
│       └── session_utils.py
```

---

## WAV 출력 스펙

### Fusion
| 항목 | 값 |
|------|-----|
| 샘플레이트 | 세션별 자동 감지 (6.4k~51.2kHz) |
| 비트 깊이 | 32-bit |
| 채널 | Mono |
| 파일명 | `YYYYMMDD_HHMMSS_HHMMSS.wav` |

### Rion
| 항목 | 값 |
|------|-----|
| 샘플레이트 | 48kHz (원본 유지) |
| 비트 깊이 | 원본 유지 |
| 채널 | 원본 유지 |
| 파일명 | 원본 파일명 그대로 (예: `NL_001_20250915_000427_....wav`) |

---

## 출력 폴더 구조

```
/mnt/audio_archive/upload_drop/{위치}/
├── extraction_plan.txt        # 추출 계획서 (최신 1개)
├── extraction_log.txt         # 추출 로그 (최신 1개)
├── N-1/
│   └── session_..._N-1_20250915_월_000/
│       ├── 20250915_000000_003000.wav   # Fusion
│       ├── 20250915_003000_010000.wav
│       └── ...
├── N-3/
│   └── session_..._N-3_20250915_월_000/
│       ├── NL_001_20250915_000427_....wav   # Rion (원본 파일명)
│       └── ...
```

---

## 실행 방법

```bash
cd /opt/mnc-system/mnc_studio
source venv/bin/activate
python audio_organizer/main_cli.py --help
```

또는 스크립트 사용:
```bash
bash scripts/audio-cli.sh extract-to-main /path/to/source --output /path/to/output
```

---

**최종 업데이트**: 2026-01-04
