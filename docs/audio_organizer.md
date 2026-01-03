# MNC Audio Organizer v1.1.0

> Fusion 소음측정기의 BID 오디오 파일을 WAV로 추출하는 CLI 도구

---

## 개요

| 항목 | 값 |
|------|-----|
| **버전** | v1.1.0 |
| **목적** | Fusion BID → WAV 추출 |
| **인터페이스** | CLI (Command Line) |
| **입력** | Fusion 세션 폴더 (N2xx ~ N5xx 장비) |
| **출력** | 32-bit mono WAV (샘플레이트 자동 감지: 6.4k~51.2kHz) |

---

## 핵심 로직 (절대 변경 금지)

### 1. BID → WAV 변환 (32-bit 피크 정규화)

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
- 검증: 미여도, 낙동, 수원 데이터에서 100% 샘플 일치 확인

**금지**: 16-bit 변환(`>> 8`) 사용 금지 - 일부 데이터에서 89% 클리핑 발생!

### 2. WAV 출력 스펙

**파일**: `src/config.py`, `src/utils/audio_config.py`

| 항목 | 값 | 비고 |
|------|-----|------|
| 샘플레이트 | **세션별 자동 감지** | 6.4k, 12.8k, 25.6k, 51.2k Hz |
| 비트 깊이 (입력) | 32-bit | `FUSION_BID_BYTES_PER_SAMPLE = 4` |
| 비트 깊이 (출력) | 32-bit | `OUTPUT_SAMPLE_WIDTH = 4` |
| 채널 | Mono | `OUTPUT_CHANNELS = 1` |
| 세그먼트 | 30분 (1800초) | `FUSION_SEGMENT_DURATION` |
| 하루 파일 수 | 48개 | - |
| 피크 정규화 상수 | 2,147,483,642 | `FUSION_FULL_SCALE` |

**샘플레이트 감지**: 세션 폴더의 `settings/configuration/*.xml`에서 `<SamplingFrequency>` 값을 읽습니다.
자세한 내용은 [fusion_audio_format.md](./fusion_audio_format.md) 참조.

---

## 사용법

### 스캔
```bash
python main.py scan /path/to/source
```

### 추출
```bash
python main.py extract /path/to/source \
    --location 대구비행장 \
    --output /mnt/audio_archive/raw_audio \
    --exclude-weekend \
    --exclude-partial
```

### 옵션
| 옵션 | 설명 |
|------|------|
| `--exclude-weekend` | 주말(토/일) 제외 |
| `--exclude-partial` | 48개 미만 파일 세션 제외 |
| `--dry-run` | 실제 변환 없이 미리보기 |
| `--no-color` | 색상 출력 비활성화 |

---

## 기능 목록

### 구현됨 (v1.1.0)

| 기능 | 설명 | 파일 |
|------|------|------|
| 세션 자동 감지 | Fusion 장비 폴더 탐색 | `detectors/fusion_detector.py` |
| 주말 제외 필터 | 토/일 제외 | `--exclude-weekend` |
| 부분 데이터 제외 | 48개 미만 파일 제외 | `--exclude-partial` |
| BID 크기 검증 | 샘플레이트별 동적 계산 | `validators/fusion_validator.py` |
| BID→WAV 변환 | 32-bit 피크 정규화 | `processors/fusion_processor.py` |
| manifest.json 생성 | 메타데이터 기록 | `utils/manifest.py` |

---

## 파일 구조

```
audio_organizer/
├── main.py                 # 진입점
├── main_cli.py             # CLI 구현
├── src/
│   ├── __init__.py
│   ├── config.py           # 상수 정의 (FUSION_FULL_SCALE 등)
│   ├── detectors/
│   │   ├── base_detector.py
│   │   └── fusion_detector.py   # 세션 감지
│   ├── processors/
│   │   ├── base_processor.py
│   │   └── fusion_processor.py  # BID→WAV 변환 (핵심!)
│   ├── validators/
│   │   └── fusion_validator.py
│   └── utils/
│       ├── audio_config.py      # 샘플레이트 감지
│       ├── date_utils.py
│       ├── manifest.py
│       ├── permissions.py
│       └── session_utils.py
```

---

## 출력 파일명 규칙

```
{YYYYMMDD}_{HHMMSS}_{HHMMSS}.wav
```

**예시**:
```
20251205_200000_203000.wav   # 2025년 12월 5일 20:00:00 ~ 20:30:00
20251205_203000_210000.wav   # 2025년 12월 5일 20:30:00 ~ 21:00:00
```

---

## 출력 폴더 구조

```
/mnt/audio_archive/raw_audio/
└── {위치}/
    └── {지점}/
        └── YYYYMMDD(요일)/
            ├── 20251205_200000_203000.wav
            ├── 20251205_203000_210000.wav
            ├── ...
            └── manifest.json
```

---

## 실행 방법

```bash
cd /opt/mnc-system/mnc_studio/audio_organizer
source ../venv/bin/activate
python main.py --help
```

---

**최종 업데이트**: 2026-01-03
