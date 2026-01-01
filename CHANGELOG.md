# Changelog

MNC Studio 도구 모음의 모든 주요 변경 사항을 기록합니다.

형식: [Keep a Changelog](https://keepachangelog.com/ko/1.0.0/)

---

## [Unreleased]

### 예정
- Audio Organizer: 로그 복사/저장 버튼
- Audio Organizer: QSettings로 경로/필터 저장
- Converter: 검증 리포트 UI 개선
- Converter: 일별 데이터 완성도 시각화

---

## Audio Organizer

### [1.0.0] - 2026-01-01

#### Added
- Fusion BID → WAV 변환 기능
- 세션 자동 감지 (Fusion 장비 폴더 탐색)
- 백그라운드 스캔 (UI 멈춤 방지)
- 주말 제외 필터
- 부분 데이터 제외 필터 (48개 미만)
- manifest.json 생성
- 숫자 정렬 (파일수 컬럼)
- 처리 중 UI 잠금 (테이블/필터 비활성화)
- 취소 기능 (별도 메시지 표시)
- 출력 폴더 열기 버튼
- 색상 로그 (ERROR/WARN/완료)
- 옵션 B 레이아웃 (테이블 중심 + 로그 하단)

#### Fixed
- 열기 버튼 너비 수정 (50 → 70)

#### Technical
- 핵심 변환: `>> 8` 시프트 (32-bit → 16-bit)
- WAV 스펙: 25,600Hz, 16-bit, mono
- UserRole 인덱스로 테이블 정렬 시 세션 참조 보존

---

## Converter

### [3.0.0] - 2026-01-01

#### Added
- Fusion .bid 파서 (Leq 데이터)
- Rion .rnd 파서 (AUTO_LP 폴더)
- 장비 자동 감지
- 수동 장비 선택 (감지 실패 시)
- Parquet 출력 (86,400행)
- CSV 출력 (검증용)
- 1/3 옥타브 밴드 (33밴드 옵션)
- 가중치 선택 (LAS, LCS, 둘 다)
- DataValidator 검증 리포트
- 좌우 스플리터 레이아웃
- 검정 로그창 (#1e1e1e)
- 색상 로그 (ERROR/WARN/정상)
- 로그 복사/저장/지우기 버튼
- 경고/에러 카운트 표시

#### Technical
- 사사오입 반올림 (ROUND_HALF_UP)
- Rion 인코딩 fallback (UTF-8 → UTF-8-SIG → CP949)
- 35컬럼 Parquet 스키마 (timestamp, spl, 33밴드)

---

## Audio Copier

### [1.0.0] - 2025-12-31

#### Added
- WAV 파일 복사 기능
- 폴더 구조 유지
- 주말 필터링

---

## 인프라

### [2026-01-01]

#### Added
- 문서화: `docs/audio_organizer.md`, `docs/converter.md`
- CHANGELOG.md 생성
- 개발 플로우 지침 (CLAUDE.md)
- 검토자 협업 프로세스


---

## 관리 지침

### 변경 시 업데이트 필수 항목

1. **핵심 로직 변경 시**: 해당 도구 문서의 "핵심 로직" 섹션 업데이트
2. **기능 추가 시**: "기능 목록" 섹션 + CHANGELOG에 기록
3. **버전 업그레이드 시**: CHANGELOG에 날짜와 함께 기록
4. **UI 변경 시**: 레이아웃 다이어그램 업데이트

### 커밋 시 함께 업데이트

```bash
# 예시: 새 기능 추가 시
git add src/app.py docs/audio_organizer.md CHANGELOG.md
git commit -m "기능 추가: 로그 저장 버튼"
```

---

**최종 업데이트**: 2026-01-01
