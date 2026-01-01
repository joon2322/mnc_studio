# MNC Audio Organizer v1.0.0

> Fusion 소음측정기의 BID 오디오 파일을 WAV로 추출하는 GUI 도구

---

## 개요

| 항목 | 값 |
|------|-----|
| **버전** | v1.0.0 |
| **목적** | Fusion BID → WAV 추출 |
| **GUI** | PyQt6 |
| **입력** | Fusion 세션 폴더 (N2xx ~ N5xx 장비) |
| **출력** | 16-bit 25.6kHz mono WAV 파일 |

---

## 핵심 로직 (절대 변경 금지)

### 1. BID → WAV 변환

**파일**: `src/processors/fusion_processor.py:131-136`

```python
# BID 파일 읽기 (32-bit little-endian signed integer)
raw_data = np.fromfile(bid_path, dtype='<i4')

# 32-bit → 16-bit 변환 (오른쪽 시프트 8비트)
# 이 방법은 클리핑 없이 전체 동적 범위를 보존함
audio_16bit = (raw_data >> 8).astype(np.int16)
```

**경고**: `np.clip()` 사용 시 54% 데이터 손실 발생!

### 2. WAV 출력 스펙

**파일**: `src/config.py:10-23`

| 항목 | 값 | 상수명 |
|------|-----|--------|
| 샘플레이트 | 25,600 Hz | `FUSION_SAMPLE_RATE` |
| 비트 깊이 (입력) | 32-bit | `FUSION_BID_BYTES_PER_SAMPLE = 4` |
| 비트 깊이 (출력) | 16-bit | `OUTPUT_SAMPLE_WIDTH = 2` |
| 채널 | Mono | `OUTPUT_CHANNELS = 1` |
| 세그먼트 | 30분 (1800초) | `FUSION_SEGMENT_DURATION` |
| 하루 파일 수 | 48개 | - |

### 3. 테이블 정렬 시 세션 인덱스 보존

**파일**: `src/app.py:562-566`

```python
# 정렬 후에도 올바른 세션 참조를 위해 원본 인덱스 저장
check_item.setData(Qt.ItemDataRole.UserRole, row)
```

---

## 기능 목록

### 구현됨 (v1.0.0)

| 기능 | 설명 | 파일 |
|------|------|------|
| 세션 자동 감지 | Fusion 장비 폴더 탐색 | `detectors/fusion_detector.py` |
| 백그라운드 스캔 | UI 멈춤 방지 | `app.py:ScanThread` |
| 주말 제외 필터 | 토/일 자동 체크 해제 | `app.py:_apply_filters` |
| 부분 데이터 제외 | 48개 미만 파일 제외 | `app.py:_apply_filters` |
| BID→WAV 변환 | >> 8 시프트 | `processors/fusion_processor.py` |
| manifest.json 생성 | 메타데이터 기록 | `utils/manifest.py` |
| 숫자 정렬 | 파일수 컬럼 정렬 | `app.py:NumericTableWidgetItem` |
| 처리 중 UI 잠금 | 테이블/필터 비활성화 | `app.py:_set_processing_state` |
| 취소 기능 | 별도 메시지 표시 | `app.py:_on_finished` |
| 출력 폴더 열기 | 완료 후 바로 접근 | `app.py:_open_output_folder` |
| 색상 로그 | ERROR/WARN/완료 색상 | `app.py:_on_log` |

### 예정 (Phase 2)

| 기능 | 설명 |
|------|------|
| 로그 복사/저장 | 지원/이력 공유용 |
| 설정 저장 (QSettings) | 최근 경로/필터 기억 |

---

## 파일 구조

```
audio_organizer/
├── main.py                 # 진입점
├── src/
│   ├── __init__.py
│   ├── config.py           # 상수 정의 (샘플레이트 등)
│   ├── app.py              # PyQt6 GUI
│   ├── detectors/
│   │   ├── __init__.py
│   │   ├── base_detector.py
│   │   └── fusion_detector.py   # 세션 감지
│   ├── processors/
│   │   ├── __init__.py
│   │   ├── base_processor.py
│   │   └── fusion_processor.py  # BID→WAV 변환 (핵심!)
│   ├── validators/
│   │   ├── __init__.py
│   │   └── fusion_validator.py
│   └── utils/
│       ├── __init__.py
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
        └── session_{날짜}_{위치}_{지점}_{측정일}_{요일}_{시작시간}/
            ├── 20251205_200000_203000.wav
            ├── 20251205_203000_210000.wav
            ├── ...
            └── manifest.json
```

---

## UI 레이아웃 (옵션 B)

```
┌─────────────────────────────────────────┐
│ [설정] 소스 경로 | 위치명 | 출력경로    │
├─────────────────────────────────────────┤
│ ☐주말제외 ☐부분제외  [전체선택] [해제]  │
│ ┌─────────────────────────────────────┐ │
│ │    세션 테이블 (메인, 크게)          │ │
│ │  선택|지점|장비|측정일|요일|파일수|상태│ │
│ └─────────────────────────────────────┘ │
├─────────────────────────────────────────┤
│ [로그창] 파란색 배경 (#0f172a)          │
├─────────────────────────────────────────┤
│ 진행률 ████████░░░  [추출시작] [취소]   │
└─────────────────────────────────────────┘
```

---

## 실행 방법

```bash
# 바탕화면 바로가기 또는
bash /opt/mnc-system/mnc_studio/scripts/run_audio_organizer.sh
```

---

**최종 업데이트**: 2026-01-01
