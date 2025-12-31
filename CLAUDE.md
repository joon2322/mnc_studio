# MNC Studio - AI Agent 지침서

> **버전 관리**: 이 문서는 MNC Studio 도구 모음의 AI 에이전트 지침을 정의합니다.

---

## 개요

MNC Studio는 군 소음측정 데이터 처리 도구 모음입니다.

| 도구 | 버전 | 설명 |
|------|------|------|
| **Audio Organizer** | v1.0.0 | Fusion BID → WAV 추출기 |
| **Audio Copier** | v1.0.0 | WAV 파일 복사기 |
| **Converter** | v3.0.0 | Parquet 변환기 (개발 중) |

---

## 디렉토리 구조

```
/opt/mnc-system/mnc_studio/
├── audio_organizer/     ← 오디오 추출기 v1.0
│   ├── src/
│   │   ├── config.py
│   │   ├── detectors/   ← 세션 감지
│   │   ├── validators/  ← 파일 검증
│   │   ├── processors/  ← BID→WAV 변환
│   │   └── utils/
│   └── main.py
├── audio_copier/        ← 오디오 복사기 v1.0
│   ├── src/
│   │   ├── config.py
│   │   ├── scanner.py
│   │   ├── copier.py
│   │   └── app.py
│   └── main.py
├── converter/           ← Parquet 변환기 v3.0
│   ├── src/
│   │   ├── config.py
│   │   ├── parsers/     ← Fusion/Rion 파서
│   │   ├── exporters/   ← Parquet/CSV 출력
│   │   └── utils/
│   └── main.py
├── scripts/             ← 실행 스크립트
└── venv/                ← 공유 가상환경
```

---

## 핵심 기술 사항

### 1. BID → WAV 변환 (Audio Organizer)

```python
# 32-bit → 16-bit 변환 (절대 클리핑 사용 금지!)
raw_data = np.fromfile(bid_path, dtype='<i4')  # 32-bit signed
audio_16bit = (raw_data >> 8).astype(np.int16)  # 오른쪽 시프트
```

**경고**: `np.clip()` 사용 시 54% 데이터 손실 발생!

### 2. 지점 vs 장비 시리얼 구분

| 구분 | 패턴 | 예시 |
|------|------|------|
| 지점 | N-?\d{1,2} | N-1, N-10, N01 |
| 장비 시리얼 | N[2-5]\d{2} | N208, N444, N510 |

### 3. 테이블 정렬 시 세션 인덱스 보존

```python
# 정렬 후에도 올바른 세션 참조를 위해 원본 인덱스 저장
item.setData(Qt.ItemDataRole.UserRole, row)
```

### 4. 사사오입 반올림 (Converter)

```python
from decimal import Decimal, ROUND_HALF_UP

def round_half_up(value, decimals=1):
    d = Decimal(str(value))
    return float(d.quantize(Decimal(10) ** -decimals, rounding=ROUND_HALF_UP))
```

---

## 출력 파일명 규칙

### Audio Organizer (WAV)
```
{YYYYMMDD}_{HHMMSS}_{HHMMSS}.wav
예: 20251205_200000_203000.wav
```

### Converter (Parquet/CSV)
```
{위치}_{차수}_{지점}_{측정일자}_{요일}_{가중치}.parquet
예: 광주비행장_1차_N-1_20251127_목_LAS.parquet
```

---

## 실행 방법

```bash
# 1. 환경 설정 (최초 1회)
bash /opt/mnc-system/mnc_studio/scripts/setup_venv.sh

# 2. 각 도구 실행
bash /opt/mnc-system/mnc_studio/scripts/run_audio_organizer.sh
bash /opt/mnc-system/mnc_studio/scripts/run_audio_copier.sh
bash /opt/mnc-system/mnc_studio/scripts/run_converter.sh
```

**GUI 환경변수**: `export DISPLAY=:1`

---

## 금지 사항

### 절대 실행 금지 명령어

```bash
❌ rm -rf /opt/mnc-system
❌ rm -rf /
❌ sudo rm -rf
```

### 코드 수정 시 주의

1. **기존 파일 우선 편집** - 새 파일 생성 최소화
2. **BID 변환 로직 변경 금지** - `>> 8` 시프트 유지
3. **테이블 정렬 로직 변경 금지** - UserRole 인덱스 유지

---

## 버전 히스토리

| 날짜 | 버전 | 변경 내용 |
|------|------|----------|
| 2025-12-31 | v1.0.0 | Audio Organizer, Copier 완성 |
| 2025-12-31 | v3.0.0 | Converter 기본 구조 완성 |

---

**최종 업데이트**: 2025-12-31
