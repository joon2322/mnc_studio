# MNC Studio

군 소음측정 데이터 처리 도구 모음

## 포함 도구

### 1. Audio Organizer v1.0.0
Fusion 소음측정기의 BID 파일을 WAV 오디오로 추출합니다.

- **입력**: Fusion 세션 폴더 (N2xx ~ N5xx 장비)
- **출력**: 16-bit 25.6kHz mono WAV 파일
- **기능**: 세션 자동 감지, 주말/부분 데이터 필터링

### 2. Audio Copier v1.0.0
추출된 WAV 파일을 다른 위치로 복사합니다.

- **입력**: Audio Organizer 출력 폴더
- **출력**: 동일 구조로 복사
- **기능**: 폴더 구조 유지, 주말 필터링

### 3. Converter v3.0.0 (개발 중)
Fusion/Rion 소음측정 데이터를 Parquet 형식으로 변환합니다.

- **지원 장비**: Fusion (.bid), Rion NX-42RT (.rnd)
- **출력**: 86,400행 Parquet (1일 = 24시간 × 60분 × 60초)
- **가중치**: LAS, LCS

## 설치

```bash
# 1. 가상환경 설정
bash /opt/mnc-system/mnc_studio/scripts/setup_venv.sh
```

## 실행

```bash
# GUI 환경 설정 (SSH 원격 접속 시)
export DISPLAY=:1

# Audio Organizer 실행
bash /opt/mnc-system/mnc_studio/scripts/run_audio_organizer.sh

# Audio Copier 실행
bash /opt/mnc-system/mnc_studio/scripts/run_audio_copier.sh

# Converter 실행
bash /opt/mnc-system/mnc_studio/scripts/run_converter.sh
```

## 요구사항

- Python 3.11+
- PyQt6
- numpy
- pandas (Converter)
- pyarrow (Converter)

## 디렉토리 구조

```
mnc_studio/
├── audio_organizer/    # BID → WAV 추출
├── audio_copier/       # WAV 복사
├── converter/          # Parquet 변환
├── scripts/            # 실행 스크립트
│   ├── run_audio_organizer.sh
│   ├── run_audio_copier.sh
│   ├── run_converter.sh
│   └── setup_venv.sh
├── venv/               # 가상환경
├── CLAUDE.md           # AI 지침
└── README.md           # 이 파일
```

## 라이선스

내부 사용 전용
