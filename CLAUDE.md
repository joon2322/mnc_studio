# MNC Studio - AI Agent 지침서

> **버전 관리**: 이 문서는 MNC Studio 도구 모음의 AI 에이전트 지침을 정의합니다.

**주의**: `AGENTS.md`는 검토자 전용 문서입니다. AI 에이전트는 수정하지 않습니다.

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

## 개발 플로우

> **원칙**: 속도보다 정확성, 안전성, 확실성

### 필수 프로세스

1. **작업 전 환경 확인** - 경로, 설정, XDG 디렉토리 등 가정하지 말고 확인
2. **검토자 협업** - 복잡하거나 환경 의존적 작업 시 검토자에게 확인 요청
3. **실제 환경 테스트** - 터미널뿐 아니라 GUI 클릭 등 실제 사용 환경에서 검증

### 검토자 협업 시점

- 시스템/경로/환경 변수 관련 작업
- 문제가 반복될 때 (같은 해결책 3회 이상 시도 금지)
- 확신이 없을 때

### 환경 확인 체크리스트 (Linux GUI)

```bash
# XDG 데스크톱 경로 확인 (한글 Ubuntu 주의!)
cat ~/.config/user-dirs.dirs | grep DESKTOP
xdg-user-dir DESKTOP

# .desktop 파일 위치 확인
ls ~/바탕화면/*.desktop  # 한글
ls ~/Desktop/*.desktop   # 영어
```

---

## GitHub 저장소

- **URL**: https://github.com/joon2322/mnc_studio
- **토큰**: ghp_p3lG... (별도 보관)
- **용도**: 코드 백업 및 버전 관리

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
| 2026-01-01 | - | 개발 플로우 지침 추가 (검토자 협업 필수화) |

---

**최종 업데이트**: 2026-01-01
