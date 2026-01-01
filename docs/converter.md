# MNC Master Converter v3.0.0

> Fusion/Rion 소음측정기 데이터를 Parquet/CSV 형식으로 변환하는 GUI 도구

---

## 개요

| 항목 | 값 |
|------|-----|
| **버전** | v3.0.0 |
| **목적** | 소음측정 데이터 → Parquet/CSV 변환 |
| **GUI** | PyQt6 |
| **지원 장비** | Fusion (.bid), Rion NX-42RT (.rnd) |
| **출력** | 86,400행 Parquet (1일 = 24시간 × 60분 × 60초) |

---

## 핵심 로직 (절대 변경 금지)

### 1. 사사오입 반올림

**파일**: `src/utils/round_utils.py`

```python
from decimal import Decimal, ROUND_HALF_UP

def round_half_up(value, decimals=1):
    d = Decimal(str(value))
    return float(d.quantize(Decimal(10) ** -decimals, rounding=ROUND_HALF_UP))
```

**주의**: Python 내장 `round()`는 은행가 반올림(짝수 반올림)이라 결과가 다름!

### 2. Fusion .bid 파일 읽기

**파일**: `src/parsers/fusion_parser.py`

```python
# BID 파일 읽기 (little-endian int16, dB * 100 저장)
data = np.fromfile(file_path, dtype='<i2')
return data.astype(float) / 100.0  # dB * 100 → dB
```

### 3. Rion .rnd 파일 읽기

**파일**: `src/parsers/rion_parser.py`

```python
# 인코딩 fallback 처리
for encoding in ['utf-8', 'utf-8-sig', 'cp949']:
    try:
        df = pd.read_csv(file_path, skiprows=1, encoding=encoding)
        break
    except UnicodeDecodeError:
        continue

# 가중치별 컬럼 선택
df['spl'] = df['Main'] if weighting == 'LAS' else df['Sub']
```

### 4. 86,400행 DataFrame 생성

**파일**: `src/parsers/base_parser.py`

```python
def create_full_day_df(self, date, include_bands=True):
    timestamps = [date + timedelta(seconds=i) for i in range(86400)]
    return pd.DataFrame({'timestamp': timestamps, 'spl': np.nan, ...})
```

---

## Parquet 스키마 (35컬럼)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `timestamp` | datetime64[ns] | KST, 필수 |
| `spl` | float64 | 전체 음압레벨, 필수 |
| `12.5Hz` ~ `20000Hz` | float64 | 1/3 옥타브 밴드 (33개) |

**전체 밴드 목록**:
```
12.5Hz, 16Hz, 20Hz, 25Hz, 31.5Hz, 40Hz, 50Hz, 63Hz, 80Hz, 100Hz,
125Hz, 160Hz, 200Hz, 250Hz, 315Hz, 400Hz, 500Hz, 630Hz, 800Hz, 1000Hz,
1250Hz, 1600Hz, 2000Hz, 2500Hz, 3150Hz, 4000Hz, 5000Hz, 6300Hz, 8000Hz,
10000Hz, 12500Hz, 16000Hz, 20000Hz
```

---

## 출력 파일명 규칙

```
{위치}_{차수}_{지점}_{측정일자}_{요일}_{가중치}.parquet
{위치}_{차수}_{지점}_{측정일자}_{요일}_{가중치}.csv
```

**구성 요소**:
- **위치**: 사이트명 (예: 광주비행장, 웅천사격장)
- **차수**: 선택적 (1차, 2차 또는 생략)
- **지점**: N-1, N-2, 이동식1, 이동식2 등
- **측정일자**: YYYYMMDD
- **요일**: _월, _화, _수, _목, _금, _토, _일
- **가중치**: LAS 또는 LCS

**예시**:
```
광주비행장_1차_N-1_20251127_목_LAS.parquet
웅천사격장_N-5_20251127_목_LCS.parquet    (차수 생략)
광주비행장_1차_이동식1_20251127_목_LAS.csv
```

---

## 지점명 변환 규칙

| 원본 폴더명 | 변환 결과 |
|------------|----------|
| `N01 지점명` | `N-1` |
| `N10 지점명` | `N-10` |
| `이동식 N01 지점명` | `이동식1` |
| `이동식 N07 지점명` | `이동식7` |

---

## 기능 목록

### 구현됨 (v3.0.0)

| 기능 | 설명 | 파일 |
|------|------|------|
| Fusion .bid 파서 | Leq 데이터 읽기 | `parsers/fusion_parser.py` |
| Rion .rnd 파서 | AUTO_LP 폴더 | `parsers/rion_parser.py` |
| 장비 자동 감지 | 폴더 구조 분석 | `parsers/*.py:find_device_folders` |
| 수동 장비 선택 | 감지 실패 시 | `app.py` 테이블 콤보박스 |
| Parquet 출력 | 86,400행 | `exporters/parquet_exporter.py` |
| CSV 출력 | 검증용 | `exporters/csv_exporter.py` |
| 1/3 옥타브 밴드 | 33밴드 옵션 | `config.py:include_bands` |
| 가중치 선택 | LAS, LCS, 둘 다 | `app.py` |
| 검증 리포트 | DataValidator | `validators/data_validator.py` |
| 색상 로그 | ERROR/WARN/완료 색상 | `app.py:on_log` |
| 로그 복사/저장 | 클립보드, 파일 | `app.py` |

### 예정 (Phase 2)

| 기능 | 설명 |
|------|------|
| 86,400행 검증 | 누락 데이터 확인 |
| 데이터 커버리지 리포트 | 일별 완성도 |
| 이상치 감지 | 비정상 값 탐지 |
| 시간 오류 감지 | 타임스탬프 검증 |

---

## 파일 구조

```
converter/
├── main.py                     # 진입점
├── src/
│   ├── __init__.py
│   ├── config.py               # ConversionConfig, 상수
│   ├── app.py                  # PyQt6 GUI (849줄)
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── base_parser.py      # 추상 베이스 클래스
│   │   ├── fusion_parser.py    # Fusion .bid 파서 (핵심!)
│   │   └── rion_parser.py      # Rion .rnd 파서 (핵심!)
│   ├── exporters/
│   │   ├── __init__.py
│   │   ├── parquet_exporter.py
│   │   └── csv_exporter.py
│   ├── validators/
│   │   ├── __init__.py
│   │   └── data_validator.py
│   └── utils/
│       ├── __init__.py
│       ├── round_utils.py      # 사사오입 반올림 (핵심!)
│       ├── date_utils.py
│       └── file_utils.py
```

---

## UI 레이아웃 (좌우 스플리터)

```
┌──────────────────────┬─────────────────────┐
│ [원본 데이터]         │ [변환 로그]          │
│ 경로 선택 + 장비 감지 │ 검정 배경 (#1e1e1e) │
│ ┌──────────────────┐ │                     │
│ │ 장비 테이블       │ │ 색상 로그:          │
│ │ 지점|이름|감지|선택│ │ - ERROR: 빨강       │
│ └──────────────────┘ │ - WARN: 노랑        │
│                      │ - 정상: 녹색         │
│ [변환 설정]           │                     │
│ 사이트명, 차수, 가중치│                     │
│                      │                     │
│ [출력 설정]           │ [복사][저장][지우기] │
│ 경로, CSV 옵션       │                     │
│                      │                     │
│ [실행]               │                     │
│ 진행률, 변환/취소 버튼│                     │
└──────────────────────┴─────────────────────┘
```

---

## 실행 방법

```bash
# 바탕화면 바로가기 또는
bash /opt/mnc-system/mnc_studio/scripts/run_converter.sh
```

---

**최종 업데이트**: 2026-01-01
